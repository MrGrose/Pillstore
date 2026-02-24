from decimal import Decimal
from uuid import uuid4

import pytest

from app.exceptions.handlers import ProductNotFoundError
from app.models.products import Product
from app.services.admin_service import AdminService


@pytest.fixture
def admin_service(db_session):
    return AdminService(db_session)


@pytest.fixture
async def product(db_session, seller_user):
    suffix = uuid4().hex[:8]
    p = Product(
        name="Admin Product",
        name_en="Admin",
        brand="B",
        price=Decimal("50.00"),
        url=f"https://admin-service-test.example/{suffix}",
        stock=0,
        seller_id=seller_user.id,
        is_active=True,
    )
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)
    return p


async def test_add_batch_admin_increments_stock(admin_service, product):
    await admin_service.add_batch_admin(
        product_id=product.id,
        quantity=20,
        expiry_date="2027-01-15",
    )
    await admin_service.session.refresh(product)
    assert product.stock == 20
    batches = await admin_service.get_batches_for_product(product.id)
    assert len(batches) == 1
    assert batches[0]["quantity"] == 20
    assert batches[0]["batch_code"] is not None


async def test_add_batch_admin_product_not_found(admin_service):
    with pytest.raises(ProductNotFoundError):
        await admin_service.add_batch_admin(
            product_id=99999,
            quantity=1,
            expiry_date=None,
        )


async def test_get_batches_for_product_empty(admin_service, product):
    result = await admin_service.get_batches_for_product(product.id)
    assert result == []


async def test_get_batches_for_product_excludes_zero_quantity(admin_service, product):
    await admin_service.add_batch_admin(product.id, 5, "2026-12-01")
    await admin_service.add_batch_admin(product.id, 0, "2027-01-01")
    await admin_service.session.commit()
    batches = await admin_service.get_batches_for_product(product.id)
    assert len(batches) == 1
    assert batches[0]["quantity"] == 5


async def test_delete_batch_admin(admin_service, product):
    await admin_service.add_batch_admin(product.id, 10, "2026-06-01")
    await admin_service.session.commit()
    batches = await admin_service.get_batches_for_product(product.id)
    batch_id = batches[0]["id"]
    await admin_service.delete_batch_admin(product_id=product.id, batch_id=batch_id)
    await admin_service.session.refresh(product)
    assert product.stock == 0
    batches_after = await admin_service.get_batches_for_product(product.id)
    assert len(batches_after) == 0


async def test_delete_batch_admin_wrong_product_raises(admin_service, product):
    await admin_service.add_batch_admin(product.id, 1, None)
    await admin_service.session.commit()
    batches = await admin_service.get_batches_for_product(product.id)
    batch_id = batches[0]["id"]
    with pytest.raises(ProductNotFoundError):
        await admin_service.delete_batch_admin(product_id=product.id + 100, batch_id=batch_id)


async def test_get_product_by_id(admin_service, product):
    got = await admin_service.get_product_by_id(product.id)
    assert got is not None
    assert got.id == product.id
    assert got.name == product.name


async def test_get_product_by_id_none(admin_service):
    assert await admin_service.get_product_by_id(99999) is None


async def test_get_stats(admin_service, product):
    stats = await admin_service.get_stats()
    assert isinstance(stats, dict)
