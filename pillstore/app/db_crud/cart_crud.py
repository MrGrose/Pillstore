from app.db_crud.base import CRUDBase
from app.models.users import User
from sqlalchemy import func, select, and_
from app.schemas.product import ProductRead
from app.models.cart_items import CartItem


class CrudCart(CRUDBase):
    
    def __init__(self, session, model) -> None:
        self.model = model
        self.session = session


    async def cart_qty(self, current_user: User | None, product_id: int, product: ProductRead) -> None:
        product.cart_qty = 0
        if current_user:
            cart_result = await self.session.scalars(
                select(self.model).where(
                    and_(
                        self.model.user_id == current_user.id,
                        self.model.product_id == product_id,
                    )
                )
            )
            cart_item = cart_result.first()
            product.cart_qty = cart_item.quantity if cart_item else 0
            
            
    
    async def cart_count(self, current_user: User | None, products: list[ProductRead]) -> int:
        cart_items = {}
        
        if current_user:
            cart_result = await self.session.scalars(
                select(self.model).where(self.model.user_id == current_user.id)
            )
            cart_items = {cart.product_id: cart.quantity for cart in cart_result.all()}
            
        cart_count = sum(cart_items.values())
        
        for product in products:
            product.cart_qty = cart_items.get(product.id, 0)
            
        return cart_count
    
    
    async def add_or_update(self, user_id: int, product_id: int, quantity: int) -> CartItem:
        cart_item = await self.get_cart_item(user_id, product_id)
        
        if cart_item:
            cart_item.quantity += quantity
            await self.session.commit()
            await self.session.refresh(cart_item)
            return cart_item
        else:
            new_item = CartItem(
                user_id=user_id,
                product_id=product_id,
                quantity=quantity
            )
            self.session.add(new_item)
            await self.session.commit()
            await self.session.refresh(new_item)
            return new_item
        
        
    async def get_cart_item(self, user_id: int, product_id: int) -> CartItem:
        result = await self.session.scalars(
            select(CartItem).where(
                and_(CartItem.user_id == user_id, CartItem.product_id == product_id)
            )
        )
        return result.first()


    async def get_cart_quantity(self, user_id: int, product_id: int) -> int:
        result = await self.session.scalar(
            select(func.sum(self.model.quantity))
            .where(self.model.user_id == user_id, self.model.product_id == product_id)
        )
        return result or 0