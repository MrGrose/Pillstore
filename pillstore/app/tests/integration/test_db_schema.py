from sqlalchemy import text

import pytest


async def test_tables_exist(db_session):
    for table in ("products", "product_batches", "batch_deductions", "orders", "order_items", "users"):
        r = await db_session.execute(
            text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = :name"
            ),
            {"name": table},
        )
        row = r.scalar_one_or_none()
        assert row is not None, f"Table {table} should exist"
