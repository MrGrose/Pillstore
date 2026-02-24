import pytest
from httpx import AsyncClient


async def test_admin_stats_unauthorized(client: AsyncClient):
    r = await client.get("/api/v2/admin/stats")
    assert r.status_code in (401, 403)


async def test_admin_stats_ok(auth_client: AsyncClient):
    r = await auth_client.get("/api/v2/admin/stats")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, dict)


async def test_admin_products_list(auth_client: AsyncClient):
    r = await auth_client.get(
        "/api/v2/admin/products",
        params={"page": 1, "page_size": 10, "active_only": True},
    )
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert "total" in data
    assert "total_active" in data
    assert "total_inactive" in data


async def test_admin_create_product_duplicate_url(auth_client: AsyncClient, db_session, seller_user):
    from uuid import uuid4
    from app.models.products import Product
    from decimal import Decimal

    dup_url = f"https://dup-url.example/{uuid4().hex[:8]}"
    p = Product(
        name="Dup",
        name_en="Dup",
        brand="B",
        price=Decimal("1.00"),
        url=dup_url,
        stock=0,
        seller_id=seller_user.id,
        is_active=True,
    )
    db_session.add(p)
    await db_session.commit()
    r = await auth_client.post(
        "/api/v2/admin/products",
        json={
            "name": "Another",
            "name_en": "",
            "brand": "B",
            "price": 10,
            "url": dup_url,
            "stock": 0,
            "is_active": True,
            "seller_id": seller_user.id,
            "category_id": [],
        },
    )
    assert r.status_code == 400


async def test_admin_delete_product_not_found(auth_client: AsyncClient):
    r = await auth_client.delete("/api/v2/admin/products/999999")
    assert r.status_code == 404
