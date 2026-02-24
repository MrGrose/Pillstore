from decimal import Decimal
from uuid import uuid4

import pytest

from app.exceptions.handlers import BusinessError, OrderNotFoundError
from app.models.orders import Order, OrderItem
from app.services.order_service import OrderService


@pytest.fixture
def order_service(db_session):
    return OrderService(db_session)


@pytest.fixture
async def product_with_batch(db_session, seller_user):
    from app.db_crud.batch_crud import CrudBatch
    from app.models.products import Product

    suffix = uuid4().hex[:8]
    p = Product(
        name="Order Product",
        name_en="Order",
        brand="B",
        price=Decimal("99.00"),
        url=f"https://order-service-test.example/{suffix}",
        stock=0,
        seller_id=seller_user.id,
        is_active=True,
    )
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)
    batch_crud = CrudBatch(db_session)
    await batch_crud.add_batch(p.id, 15, "2026-12-01", None)
    await db_session.commit()
    await db_session.refresh(p)
    p.stock = 15
    await db_session.flush()
    await db_session.commit()
    await db_session.refresh(p)
    return p


@pytest.fixture
async def pending_order(db_session, seller_user, product_with_batch):
    order = Order(
        user_id=seller_user.id,
        status="pending",
        total_amount=Decimal("198.00"),
    )
    db_session.add(order)
    await db_session.flush()
    item = OrderItem(
        order_id=order.id,
        product_id=product_with_batch.id,
        quantity=2,
        unit_price=product_with_batch.price,
        total_price=product_with_batch.price * 2,
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(order)
    await db_session.refresh(item)
    return order


async def test_confirm_payment_deducts_fifo_and_sets_paid(
    order_service, pending_order, product_with_batch, seller_user
):
    order_id = pending_order.id
    user_id = seller_user.id
    order = await order_service.confirm_payment(order_id, user_id)
    assert order.status == "paid"
    await order_service.session.refresh(product_with_batch)
    assert product_with_batch.stock == 13  # 15 - 2
    total_in_batches = await order_service.batch_crud.get_total_stock_from_batches(
        product_with_batch.id
    )
    assert total_in_batches == 13


async def test_confirm_payment_order_not_found(order_service, seller_user):
    with pytest.raises(OrderNotFoundError):
        await order_service.confirm_payment(99999, seller_user.id)


async def test_confirm_payment_wrong_user_raises(
    order_service, pending_order, db_session, seller_user
):
    from app.core.auth_utils import hash_password
    from app.db_crud.user_crud import CrudUser
    from app.models.users import User as UserModel

    other = await CrudUser(db_session, UserModel).create({
        "email": f"other-{uuid4().hex[:8]}@test.ru",
        "hashed_password": hash_password("x"),
        "is_active": True,
        "role": "buyer",
    })
    await db_session.commit()
    await db_session.refresh(other)
    with pytest.raises(BusinessError, match="Нет доступа"):
        await order_service.confirm_payment(pending_order.id, other.id)


async def test_confirm_payment_already_paid_raises(
    order_service, pending_order, seller_user
):
    await order_service.confirm_payment(pending_order.id, seller_user.id)
    with pytest.raises(BusinessError, match="уже подтвержден"):
        await order_service.confirm_payment(pending_order.id, seller_user.id)
