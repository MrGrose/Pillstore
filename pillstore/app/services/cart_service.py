from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db_crud.cart_crud import CrudCart
from app.models.cart_items import CartItem 
from app.models.users import User
from app.schemas.product import ProductRead
from app.models.products import Product
from app.db_crud.products_crud import CrudProduct



class CartService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.crud = CrudCart(session=session, model=CartItem)
        self.product_crud = CrudProduct(session=session, model=Product)
    
    async def cart_count(self, user: User | None, products: list[ProductRead]) -> int:
        """Прокси на CRUD (пока без доп. логики)."""
        return await self.crud.cart_count(user, products)
    
    async def add_to_cart(self, user: User, product_id: int, quantity: int):
        # 🆗 Твой новый метод!
        current_qty = await self.crud.get_cart_quantity(user.id, product_id)
        
        # Stock
        product = await self.product_crud.get_by_id(product_id)
        
        # БИЗНЕС
        total_qty = current_qty + quantity
        if total_qty > product.stock:
            raise HTTPException(400, f"Макс еще: {product.stock - current_qty}")
        
        # Сохранить
        await self.crud.add_or_update(user.id, product_id, total_qty)
        return {"cart_qty": total_qty}