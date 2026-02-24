import pytest
from httpx import AsyncClient


async def test_health(client: AsyncClient):
    r = await client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "healthy"


async def test_get_products_list_pagination(client: AsyncClient):
    r = await client.get("/api/v2/products", params={"page": 1, "page_size": 5})
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert "total" in data
    assert data["page"] == 1
    assert data["page_size"] == 5


async def test_get_product_not_found(client: AsyncClient):
    r = await client.get("/api/v2/products/999999")
    assert r.status_code == 404


async def test_get_product_stock_not_found(client: AsyncClient):
    r = await client.get("/api/v2/products/stock/999999")
    assert r.status_code == 404


async def test_get_product_stock_ok(client: AsyncClient, db_session, seller_user):
    from uuid import uuid4
    from app.models.products import Product
    from decimal import Decimal

    p = Product(
        name="Stock Test",
        name_en="Stock",
        brand="B",
        price=Decimal("1.00"),
        url=f"https://stock-api-test.example/{uuid4().hex[:8]}",
        image_url="",
        stock=7,
        seller_id=seller_user.id,
        is_active=True,
    )
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)
    r = await client.get(f"/api/v2/products/stock/{p.id}")
    assert r.status_code == 200
    data = r.json()
    assert data["product_id"] == p.id
    assert data["stock"] == 7
    assert data["in_stock"] is True


async def test_get_product_by_id_ok(client: AsyncClient, db_session, seller_user):
    from uuid import uuid4
    from app.models.products import Product
    from decimal import Decimal

    p = Product(
        name="Detail Test",
        name_en="Detail",
        brand="B",
        price=Decimal("2.00"),
        url=f"https://detail-api-test.example/{uuid4().hex[:8]}",
        image_url="",
        stock=1,
        seller_id=seller_user.id,
        is_active=True,
    )
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)
    r = await client.get(f"/api/v2/products/{p.id}")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == p.id
    assert data["name"] == p.name
    assert data["stock"] == 1
