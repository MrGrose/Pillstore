from decimal import Decimal
from uuid import uuid4

import pytest

from app.db_crud.batch_crud import CrudBatch
from app.models.orders import Order, OrderItem
from app.models.products import Product
from app.services.admin_service import AdminService
from app.services.order_service import OrderService


@pytest.fixture
async def product(db_session, seller_user):
    suffix = uuid4().hex[:8]
    p = Product(
        name="Integration Product",
        name_en="Int",
        brand="B",
        price=Decimal("10.00"),
        url=f"https://integration-flow.example/{suffix}",
        stock=0,
        seller_id=seller_user.id,
        is_active=True,
    )
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)
    return p


async def test_full_batch_order_payment_flow(db_session, seller_user, product):
    admin_svc = AdminService(db_session)
    order_svc = OrderService(db_session)
    batch_crud = CrudBatch(db_session)

    # Партии с разными сроками (FIFO: сначала 2026-06, потом 2026-12)
    await admin_svc.add_batch_admin(product.id, 5, "2026-06-01")
    await admin_svc.add_batch_admin(product.id, 10, "2026-12-01")
    await db_session.commit()
    await db_session.refresh(product)
    assert product.stock == 15

    # Заказ с одной позицией (7 шт.)
    order = Order(
        user_id=seller_user.id,
        status="pending",
        total_amount=Decimal("70.00"),
    )
    db_session.add(order)
    await db_session.flush()
    item = OrderItem(
        order_id=order.id,
        product_id=product.id,
        quantity=7,
        unit_price=product.price,
        total_price=product.price * 7,
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(order)
    await db_session.refresh(item)

    # Подтверждение оплаты → списание FIFO
    confirmed = await order_svc.confirm_payment(order.id, seller_user.id)
    assert confirmed.status == "paid"

    await db_session.refresh(product)
    assert product.stock == 8  # 15 - 7

    batches = await batch_crud.get_batches_by_product(product.id)
    # Первая партия (5) полностью израсходована, вторая: 10 - 2 = 8
    by_expiry = sorted(batches, key=lambda b: b.expiry_date or "")
    assert by_expiry[0].quantity == 0
    assert by_expiry[1].quantity == 8
    total_in_batches = await batch_crud.get_total_stock_from_batches(product.id)
    assert total_in_batches == 8
