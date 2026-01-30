from fastapi import APIRouter, Depends, status, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_, select, update, delete

from app.core.deps import get_db
from app.models.products import Product
from app.schemas.product import ProductSchema, ProductCreate, ProductImportList

from app.services.utils import save_image_from_url, save_product_image, remove_product_image
from app.core.security import get_current_seller, get_current_user_import
from app.models.users import User as UserModel
from app.models.categories import Category
from app.schemas.category import CategoryCreate, CategoriesSchema, CategoryRead

from app.models.associations import product_categories

router = APIRouter(prefix="/api/v1", tags=["API products"])



@router.get("/products", response_model=list[ProductSchema])
async def get_products(session: AsyncSession = Depends(get_db)):
    result = select(Product).where(Product.is_active.is_(True))
    products = (await session.scalars(result)).all()
    return products


@router.post("/product", status_code=status.HTTP_201_CREATED)
async def create_product(
    product: ProductCreate = Depends(ProductCreate.as_form), 
    db: AsyncSession = Depends(get_db),
    image: UploadFile | None = File(None),
    current_user: UserModel = Depends(get_current_seller)
):
    
    result = await db.scalars(select(Product).where(Product.url == product.url))
    if result.first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Товар с таким URL уже существует")
    image_url = await save_product_image(image) if image else None
    
    db_product = Product(**product.model_dump(), image_url=image_url, seller_id=current_user.id)
    db.add(db_product)
    await db.commit()
    await db.refresh(db_product)
    return db_product


@router.delete("/{product_id}", response_model=ProductSchema)
async def delete_product(
    product_id: int,
    db: AsyncSession = Depends(get_db)
):
    result = await db.scalars(
        select(Product).where(Product.id == product_id, Product.is_active == True)
    )
    product = result.first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Продукт не найден или не активен")
    await db.execute(
        update(Product).where(Product.id == product_id).values(is_active=False)
    )
    remove_product_image(product.image_url)

    await db.commit()
    await db.refresh(product)
    return product


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_all_products(
    db: AsyncSession = Depends(get_db),
):
    await db.execute(delete(Product))
    await db.commit()


@router.put("/{product_id}", response_model=ProductSchema)
async def update_product(
        product_id: int,
        product: ProductCreate = Depends(ProductCreate.as_form),
        image: UploadFile | None = File(None),
        db: AsyncSession = Depends(get_db),
):
    result = await db.scalars(select(Product).where(Product.id == product_id))
    db_product = result.first()
    if not db_product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Продукт не найден")

    category_result = await db.scalars(
        select(Category).where(Category.id == product.category_id,
                                    Category.is_active == True)
    )
    if not category_result.first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Категория не найдена или неактивна")

    await db.execute(
        update(Product).where(Product.id == product_id).values(**product.model_dump())
    )

    if image:
        remove_product_image(db_product.image_url)
        db_product.image_url = await save_product_image(image)

    await db.commit()
    await db.refresh(db_product)
    return db_product


# Категории

@router.get("/categories", response_model=list[CategoriesSchema])
async def get_all_categories(session: AsyncSession = Depends(get_db)):
    result = select(Category).where(Category.is_active.is_(True))
    categories = (await session.scalars(result)).all()
    return categories


@router.post("/category", response_model=CategoryRead, status_code=201)
async def create_category(
    category: CategoryCreate,
    db: AsyncSession = Depends(get_db),
):
    if await db.scalar(select(Category).where(Category.name == category.name)):
        raise HTTPException(400, "Категория уже существует")
    
    if category.parent_id:
        parent = await db.scalar(
            select(Category).where(Category.id == category.parent_id, Category.is_active == True)
        )
        if not parent:
            raise HTTPException(400, "Родитель не найден")
    
    db_category = Category(**category.model_dump())
    db.add(db_category)
    await db.commit()
    await db.refresh(db_category)
    return db_category



@router.put("/{category_id}", response_model=CategoriesSchema)
async def update_category(category_id: int, category: CategoryCreate, db: AsyncSession = Depends(get_db)):
    stmt = select(Category).where(Category.id == category_id,
                                       Category.is_active == True)
    result = await db.scalars(stmt)
    db_category = result.first()
    if not db_category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Категория не найдена")

    if category.parent_id is not None:
        parent_stmt = select(Category).where(Category.id == category.parent_id,
                                                  Category.is_active == True)
        parent_result = await db.scalars(parent_stmt)
        parent = parent_result.first()
        if not parent:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Родительская категория не найдена")
        if parent.id == category_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Категория не может быть своей собственной родительской")

    update_data = category.model_dump(exclude_unset=True)
    await db.execute(
        update(Category)
        .where(Category.id == category_id)
        .values(**update_data)
    )
    await db.commit()
    return db_category


@router.delete("/{category_id}", response_model=CategoriesSchema)
async def delete_category(category_id: int, db: AsyncSession = Depends(get_db)):
    """
    Выполняет мягкое удаление категории по её ID, устанавливая is_active = False.
    """
    stmt = select(Category).where(Category.id == category_id,
                                       Category.is_active == True)
    result = await db.scalars(stmt)
    db_category = result.first()
    if not db_category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Категория не найдена")

    await db.execute(
        update(Category)
        .where(Category.id == category_id)
        .values(is_active=False)
    )
    await db.commit()
    return db_category


@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_all_categories(
    db: AsyncSession = Depends(get_db),
):
    await db.execute(delete(product_categories))
    await db.execute(delete(Category))
    await db.commit()
    
# -----------

@router.post("/import", status_code=status.HTTP_201_CREATED)
async def import_products(
    import_data: ProductImportList,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user_import)
):
    created = []
    for product_data in import_data.products:
        result = await db.scalars(select(Product).where(Product.url == product_data.url))
        if result.first():
            continue
        
        image_url = await save_image_from_url(product_data.images) if product_data.images and product_data.images.startswith('http') else product_data.images
        
        categories = []
        parent = None
        for cat_name in product_data.category_path[1:]:
            cat_result = await db.scalars(
                select(Category).where(
                    or_(Category.name == cat_name, Category.name.ilike(f"%{cat_name}%"))
                )
            )
            cat = cat_result.first()
            if not cat:
                cat = Category(name=cat_name, parent_id=parent.id if parent else None, is_active=True)
                db.add(cat)
                await db.flush()
            categories.append(cat)
            parent = cat
        
        db_product = Product(
            name=product_data.name,
            name_en=product_data.name_en,
            brand=product_data.brand,
            price=product_data.price,
            url=product_data.url,
            image_url=image_url,
            description_left=product_data.description_left,
            description_right=product_data.description_right,
            stock=10,
            seller_id=current_user.id,
            category_id=[cat.id for cat in categories],
            categories=categories,
            mpn=product_data.mpn
        )
        db.add(db_product)
        created.append(db_product)
    
    await db.commit()
    return {"imported": len(created), "skipped": len(import_data.products) - len(created)}


# -----------

# Ручка добавление товара

# @router.post("/cart/add")
# async def add_to_cart(
#     product_id: int = Form(...),
#     quantity: int = Form(1),
#     db: AsyncSession = Depends(get_db),
#     current_user: UserModel = Depends(get_current_user),
# ):
#     cart_svc = CartService(db)
#     # product_svc = ProductService(db)
#     # product = await product_svc.get_active_product(product_id)
#     # print(f'================== type {product}')
#     # print(f'==========product {product}')
#     result = await db.scalars(
#         select(Product).where(Product.id == product_id, Product.is_active.is_(True))
#     )
#     product = result.first()
#     if not product:
#         raise HTTPException(status.HTTP_404_NOT_FOUND, "Товар не найден")
#     print(f'================== type {type(result)}')
#     print(f'==========result {result}')
#     cart_result = await db.scalars(
#         select(CartItemModel)
#         .where(
#             and_(
#                 CartItemModel.user_id == current_user.id,
#                 CartItemModel.product_id == product_id
#             )
#         )
#     )
#     cart_item = cart_result.first()

#     if cart_item:
#         cart_item.quantity += quantity
#         cart_item.updated_at = datetime.utcnow()
#     else:
#         cart_item = CartItemModel(
#             user_id=current_user.id,
#             product_id=product_id,
#             quantity=quantity
#         )
#         db.add(cart_item)

#     await db.commit()
#     await db.refresh(cart_item)

#     return RedirectResponse(url="/products", status_code=303)


# Ручка для отображения списка заказов
# @router.get("/", response_model=OrderList)
# async def list_orders(
#     page: int = Query(1, ge=1),
#     page_size: int = Query(10, ge=1, le=100),
#     db: AsyncSession = Depends(get_db),
#     current_user: UserModel = Depends(get_current_user),
# ):

#     total = await db.scalar(
#         select(func.count(OrderModel.id)).where(OrderModel.user_id == current_user.id)
#     )
#     result = await db.scalars(
#         select(OrderModel)
#         .options(selectinload(OrderModel.items).selectinload(OrderItemModel.product))
#         .where(OrderModel.user_id == current_user.id)
#         .order_by(OrderModel.created_at.desc())
#         .offset((page - 1) * page_size)
#         .limit(page_size)
#     )
#     orders = result.all()

#     return OrderList(items=orders, total=total or 0, page=page, page_size=page_size)