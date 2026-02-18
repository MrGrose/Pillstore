from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.models.batches import BatchDeduction, ProductBatch
from app.models.orders import OrderItem
from app.models.products import Product


class CrudBatch:
    def __init__(self, session):
        self.session = session

    async def get_batches_by_product(
        self, product_id: int, order_by_expiry_asc: bool = True
    ) -> list[ProductBatch]:
        stmt = (
            select(ProductBatch)
            .where(ProductBatch.product_id == product_id)
            .options(selectinload(ProductBatch.deductions))
        )
        if order_by_expiry_asc:
            stmt = stmt.order_by(
                ProductBatch.expiry_date.asc(),
                ProductBatch.id.asc(),
            )
        result = await self.session.scalars(stmt)
        return list(result.all())

    async def get_total_stock_from_batches(self, product_id: int) -> int:
        stmt = select(func.coalesce(func.sum(ProductBatch.quantity), 0)).where(
            ProductBatch.product_id == product_id
        )
        r = await self.session.scalar(stmt)
        return int(r) if r is not None else 0

    async def add_batch(
        self,
        product_id: int,
        quantity: int,
        expiry_date: str | None = None,
        batch_code: str | None = None,
    ) -> ProductBatch:
        from datetime import datetime as dt

        exp = None
        if expiry_date:
            try:
                exp = dt.strptime(expiry_date, "%Y-%m-%d").date()
            except ValueError:
                pass
        batch = ProductBatch(
            product_id=product_id,
            quantity=quantity,
            expiry_date=exp,
            batch_code=batch_code,
        )
        self.session.add(batch)
        await self.session.flush()
        if batch.batch_code is None:
            batch.batch_code = f"{product_id}-{batch.id}"
            self.session.add(batch)
        product = await self.session.get(Product, product_id)
        if product:
            product.stock = (product.stock or 0) + quantity
        return batch

    async def deduct_fifo(
        self,
        product_id: int,
        quantity: int,
        order_id: int,
        order_item_id: int,
    ) -> list[tuple[int, int]]:
        batches = await self.get_batches_by_product(product_id, order_by_expiry_asc=True)
        product = await self.session.get(Product, product_id)
        if not product:
            raise ValueError(f"Product {product_id} не найден")
        total_available = sum(b.quantity for b in batches) if batches else (product.stock or 0)
        if total_available < quantity:
            raise ValueError(
                f"Недостаточно остатков для product_id={product_id}: "
                f"нужно {quantity}, доступно {total_available}"
            )
        if not batches:
            product.stock = (product.stock or 0) - quantity
            return []
        remaining = quantity
        deductions_created: list[tuple[int, int]] = []
        for batch in batches:
            if remaining <= 0 or batch.quantity <= 0:
                continue
            take = min(remaining, batch.quantity)
            batch.quantity -= take
            remaining -= take
            d = BatchDeduction(
                batch_id=batch.id,
                order_id=order_id,
                order_item_id=order_item_id,
                quantity=take,
            )
            self.session.add(d)
            deductions_created.append((batch.id, take))
            if remaining <= 0:
                break
        product.stock = (product.stock or 0) - quantity
        return deductions_created

    async def return_deductions_for_order_item(self, order_item: OrderItem) -> None:
        stmt = select(BatchDeduction).where(
            BatchDeduction.order_item_id == order_item.id
        )
        result = await self.session.scalars(stmt)
        deductions = list(result.all())
        if deductions:
            for ded in deductions:
                batch = await self.session.get(ProductBatch, ded.batch_id)
                if batch:
                    batch.quantity += ded.quantity
                await self.session.delete(ded)
            product = await self.session.get(Product, order_item.product_id)
            if product:
                product.stock = (product.stock or 0) + order_item.quantity
        else:
            product = await self.session.get(Product, order_item.product_id)
            if product:
                product.stock = (product.stock or 0) + order_item.quantity
        await self.session.flush()

    async def get_deductions_by_batch(self, batch_id: int) -> list[BatchDeduction]:
        stmt = select(BatchDeduction).where(
            BatchDeduction.batch_id == batch_id
        ).order_by(BatchDeduction.created_at.desc())
        result = await self.session.scalars(stmt)
        return list(result.all())

    async def delete_batch(self, batch_id: int) -> int:
        batch = await self.session.get(ProductBatch, batch_id)
        if not batch:
            raise ValueError(f"Партия {batch_id} не найдена")
        product = await self.session.get(Product, batch.product_id)
        if product:
            product.stock = max(0, (product.stock or 0) - batch.quantity)
        await self.session.delete(batch)
        await self.session.flush()
        return batch.product_id
