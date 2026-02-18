from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db_crud.batch_crud import CrudBatch
from app.models.batches import BatchDeduction, ProductBatch
from app.models.orders import Order, OrderItem
from app.models.products import Product
from app.models.users import User as UserModel


@pytest.fixture
async def crud(db_session):
    return CrudBatch(db_session)


@pytest.fixture
async def seller(db_session):
    from app.core.auth_utils import hash_password
    from app.db_crud.user_crud import CrudUser

    suffix = uuid4().hex[:8]
    crud_user = CrudUser(db_session, UserModel)
    u = await crud_user.create({
        "email": f"batch-seller-{suffix}@test.ru",
        "hashed_password": hash_password("x"),
        "is_active": True,
        "role": "seller",
    })
    await db_session.commit()
    await db_session.refresh(u)
    return u


@pytest.fixture
async def product(db_session, seller):
    suffix = uuid4().hex[:8]
    p = Product(
        name="Test Product",
        name_en="Test",
        brand="Brand",
        price=Decimal("100.00"),
        url=f"https://batch-test-product.example/{suffix}",
        stock=0,
        seller_id=seller.id,
        is_active=True,
    )
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)
    return p


@pytest.fixture
async def order_with_item(db_session, seller, product):
    order = Order(user_id=seller.id, status="pending", total_amount=Decimal("0"))
    db_session.add(order)
    await db_session.flush()
    item = OrderItem(
        order_id=order.id,
        product_id=product.id,
        quantity=2,
        unit_price=product.price,
        total_price=product.price * 2,
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(order)
    await db_session.refresh(item)
    return order, item


async def test_add_batch_increments_stock(crud, product):
    batch = await crud.add_batch(
        product_id=product.id,
        quantity=10,
        expiry_date="2026-12-01",
        batch_code=None,
    )
    await crud.session.commit()
    assert batch.id is not None
    assert batch.quantity == 10
    assert batch.expiry_date == date(2026, 12, 1)
    assert batch.batch_code == f"{product.id}-{batch.id}"

    await crud.session.refresh(product)
    assert product.stock == 10


async def test_add_batch_with_custom_code(crud, product):
    batch = await crud.add_batch(
        product_id=product.id,
        quantity=5,
        expiry_date=None,
        batch_code="CUSTOM-001",
    )
    await crud.session.commit()
    assert batch.batch_code == "CUSTOM-001"
    await crud.session.refresh(product)
    assert product.stock == 5


async def test_get_total_stock_from_batches(crud, product):
    await crud.add_batch(product.id, 3, "2026-06-01", None)
    await crud.add_batch(product.id, 7, "2027-01-01", None)
    await crud.session.commit()
    total = await crud.get_total_stock_from_batches(product.id)
    assert total == 10


async def test_get_batches_by_product_order_expiry(crud, product):
    await crud.add_batch(product.id, 1, "2027-01-01", None)
    await crud.add_batch(product.id, 1, "2026-06-01", None)
    await crud.session.commit()
    batches = await crud.get_batches_by_product(product.id, order_by_expiry_asc=True)
    assert len(batches) == 2
    assert batches[0].expiry_date <= batches[1].expiry_date
    assert batches[0].expiry_date == date(2026, 6, 1)


async def test_deduct_fifo_creates_deductions_and_decreases_batches(
    crud, product, order_with_item
):
    order, item = order_with_item
    await crud.add_batch(product.id, 5, "2026-06-01", None)
    await crud.add_batch(product.id, 5, "2027-06-01", None)
    await crud.session.commit()
    await crud.session.refresh(product)
    product.stock = 10
    await crud.session.flush()

    deductions = await crud.deduct_fifo(
        product_id=product.id,
        quantity=4,
        order_id=order.id,
        order_item_id=item.id,
    )
    await crud.session.commit()

    assert len(deductions) >= 1
    total_deducted = sum(qty for _, qty in deductions)
    assert total_deducted == 4

    batches = await crud.get_batches_by_product(product.id)
    first_batch = next(b for b in batches if b.expiry_date == date(2026, 6, 1))
    assert first_batch.quantity == 1  # 5 - 4

    await crud.session.refresh(product)
    assert product.stock == 6  # 10 - 4


async def test_deduct_fifo_insufficient_raises(crud, product, order_with_item):
    order, item = order_with_item
    await crud.add_batch(product.id, 2, "2026-06-01", None)
    await crud.session.commit()

    with pytest.raises(ValueError, match="Недостаточно остатков"):
        await crud.deduct_fifo(
            product_id=product.id,
            quantity=10,
            order_id=order.id,
            order_item_id=item.id,
        )


async def test_return_deductions_for_order_item_restores_stock(
    crud, product, order_with_item
):
    order, item = order_with_item
    await crud.add_batch(product.id, 10, "2026-06-01", None)
    await crud.session.commit()
    await crud.session.refresh(product)
    product.stock = 10
    await crud.session.flush()

    qty = item.quantity  # 2 из order_with_item
    await crud.deduct_fifo(product.id, qty, order.id, item.id)
    await crud.session.commit()

    await crud.session.refresh(item)
    await crud.return_deductions_for_order_item(item)
    await crud.session.commit()

    batches = await crud.get_batches_by_product(product.id)
    assert sum(b.quantity for b in batches) == 10
    await crud.session.refresh(product)
    assert product.stock == 10


async def test_delete_batch_decreases_product_stock(crud, product):
    await crud.add_batch(product.id, 7, "2026-12-01", None)
    await crud.session.commit()
    await crud.session.refresh(product)
    assert product.stock == 7

    batches = await crud.get_batches_by_product(product.id)
    batch_id = batches[0].id
    await crud.delete_batch(batch_id)
    await crud.session.commit()

    await crud.session.refresh(product)
    assert product.stock == 0
    r = await crud.session.scalar(select(ProductBatch).where(ProductBatch.id == batch_id))
    assert r is None


async def test_delete_batch_nonexistent_raises(crud):
    with pytest.raises(ValueError, match="Партия .* не найдена"):
        await crud.delete_batch(99999)
