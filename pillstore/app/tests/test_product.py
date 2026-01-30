import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from app.main import app 
from app.core.deps import get_db
from app.core.security import get_current_user_optional


@pytest.fixture
def client():
    return TestClient(app)


@pytest.mark.asyncio
async def test_product_detail_no_user(client):
    mock_db = AsyncMock()
    
    # Переопределяем зависимости app
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user_optional] = lambda: None
    
    # Мокаем сервисы напрямую в функции роутера
    with patch('app.routers.products.ProductService') as mock_product_cls, \
         patch('app.routers.products.CartService') as mock_cart_cls:
        
        mock_product_svc = AsyncMock()
        mock_product_svc.get_product_detail.return_value = MagicMock(id=1, name="Test Product")
        mock_cart_svc = AsyncMock()
        mock_cart_svc.cart_count.return_value = 0
        
        mock_product_cls.return_value = mock_product_svc
        mock_cart_cls.return_value = mock_cart_svc
        
        response = client.get("/products/1")
    
    assert response.status_code == 200
    assert response.template.name == "product_detail.html"
    context = response.context
    assert context["product"].id == 1
    assert context["current_user"] is None
    assert context["cart_count"] == 0
    
    app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_product_detail_with_user(client):
    mock_db = AsyncMock()
    mock_user = MagicMock(id=123, username="test")
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user_optional] = lambda: mock_user
    
    with patch('app.routers.products.ProductService') as mock_product_cls, \
         patch('app.routers.products.CartService') as mock_cart_cls:
        
        mock_product_svc = AsyncMock()
        mock_product_svc.get_product_detail.return_value = MagicMock(id=1, name="Test Product")
        mock_cart_svc = AsyncMock()
        mock_cart_svc.cart_count.return_value = 5
        
        mock_product_cls.return_value = mock_product_svc
        mock_cart_cls.return_value = mock_cart_svc
        
        response = client.get("/products/1")
    
    assert response.status_code == 200
    context = response.context
    assert context["current_user"].id == 123
    assert context["cart_count"] == 5
    app.dependency_overrides.clear()
    
    
    
# Тест на не найденный товар