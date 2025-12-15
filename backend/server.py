from fastapi import FastAPI, APIRouter, HTTPException, Depends, Header
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional
import uuid
from datetime import datetime, timezone, timedelta
import secrets
import hashlib
from enum import Enum
from emergentintegrations.llm.chat import LlmChat, UserMessage

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============= ENUMS =============
class OrderStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"

class PaymentMethod(str, Enum):
    COD = "cod"
    ACCOUNT = "account"

class PaymentStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"

# ============= MODELS =============

# Dealer/User Models
class DealerCreate(BaseModel):
    name: str
    phone: str
    email: EmailStr
    business_name: str
    address: str
    gst_number: Optional[str] = None

class Dealer(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    phone: str
    email: str
    business_name: str
    address: str
    gst_number: Optional[str] = None
    credit_limit: float = 100000.0  # Default credit limit
    outstanding_balance: float = 0.0
    auth_token: Optional[str] = None
    otp: Optional[str] = None
    otp_expires_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# Authentication Models
class SendOTPRequest(BaseModel):
    phone: str

class VerifyOTPRequest(BaseModel):
    phone: str
    otp: str

class AuthResponse(BaseModel):
    token: str
    dealer: Dealer

# Product Models
class Product(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str
    category: str
    grade: str  # e.g., "43", "53"
    packaging: str  # e.g., "50kg bag"
    price: float
    stock: int
    image_url: str
    specifications: dict = {}
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# Cart Models
class CartItemCreate(BaseModel):
    product_id: str
    quantity: int = 1

class CartItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    dealer_id: str
    product_id: str
    quantity: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class CartItemWithProduct(BaseModel):
    id: str
    product: Product
    quantity: int
    subtotal: float

# Order Models
class OrderCreate(BaseModel):
    payment_method: PaymentMethod
    delivery_address: str
    notes: Optional[str] = None

class OrderItem(BaseModel):
    product_id: str
    product_name: str
    quantity: int
    price: float
    subtotal: float

class Order(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    order_number: str
    dealer_id: str
    items: List[OrderItem]
    total_amount: float
    payment_method: PaymentMethod
    payment_status: PaymentStatus = PaymentStatus.PENDING
    order_status: OrderStatus = OrderStatus.PENDING
    delivery_address: str
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# Dashboard Models
class DashboardStats(BaseModel):
    total_orders: int
    pending_orders: int
    delivered_orders: int
    total_spent: float
    credit_available: float
    outstanding_balance: float

# Chat Models
class ChatMessage(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str

# ============= HELPER FUNCTIONS =============

def generate_otp() -> str:
    """Generate a 6-digit OTP"""
    return ''.join([str(secrets.randbelow(10)) for _ in range(6)])

def generate_token() -> str:
    """Generate a secure token"""
    return secrets.token_urlsafe(32)

def generate_order_number() -> str:
    """Generate unique order number"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_suffix = secrets.token_hex(3).upper()
    return f"ORD-{timestamp}-{random_suffix}"

async def get_current_dealer(authorization: Optional[str] = Header(None)) -> Dealer:
    """Dependency to get current authenticated dealer"""
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = authorization.replace('Bearer ', '')
    dealer_doc = await db.dealers.find_one({"auth_token": token}, {"_id": 0})
    
    if not dealer_doc:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    return Dealer(**dealer_doc)

# ============= AUTHENTICATION ROUTES =============

@api_router.post("/auth/register", response_model=Dealer)
async def register_dealer(dealer_data: DealerCreate):
    """Register a new dealer"""
    # Check if phone already exists
    existing = await db.dealers.find_one({"phone": dealer_data.phone})
    if existing:
        raise HTTPException(status_code=400, detail="Phone number already registered")
    
    dealer = Dealer(**dealer_data.model_dump())
    doc = dealer.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    
    await db.dealers.insert_one(doc)
    return dealer

@api_router.post("/auth/send-otp")
async def send_otp(request: SendOTPRequest):
    """Send OTP to dealer's phone"""
    dealer_doc = await db.dealers.find_one({"phone": request.phone}, {"_id": 0})
    
    if not dealer_doc:
        raise HTTPException(status_code=404, detail="Phone number not registered")
    
    otp = generate_otp()
    otp_expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
    
    # Update dealer with OTP
    await db.dealers.update_one(
        {"phone": request.phone},
        {"$set": {
            "otp": otp,
            "otp_expires_at": otp_expires_at.isoformat()
        }}
    )
    
    # In production, send OTP via SMS using Twilio or similar
    # For now, return OTP in response (DEVELOPMENT ONLY)
    logger.info(f"OTP for {request.phone}: {otp}")
    
    return {"message": "OTP sent successfully", "otp": otp}  # Remove otp in production

@api_router.post("/auth/verify-otp", response_model=AuthResponse)
async def verify_otp(request: VerifyOTPRequest):
    """Verify OTP and login"""
    dealer_doc = await db.dealers.find_one({"phone": request.phone}, {"_id": 0})
    
    if not dealer_doc:
        raise HTTPException(status_code=404, detail="Phone number not registered")
    
    # Check OTP
    if dealer_doc.get("otp") != request.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    
    # Check OTP expiry
    otp_expires_at = datetime.fromisoformat(dealer_doc["otp_expires_at"])
    if datetime.now(timezone.utc) > otp_expires_at:
        raise HTTPException(status_code=400, detail="OTP expired")
    
    # Generate auth token
    token = generate_token()
    
    # Update dealer
    await db.dealers.update_one(
        {"phone": request.phone},
        {"$set": {
            "auth_token": token,
            "otp": None,
            "otp_expires_at": None
        }}
    )
    
    dealer_doc["auth_token"] = token
    if 'created_at' in dealer_doc and isinstance(dealer_doc['created_at'], str):
        dealer_doc['created_at'] = datetime.fromisoformat(dealer_doc['created_at'])
    
    dealer = Dealer(**dealer_doc)
    
    return AuthResponse(token=token, dealer=dealer)

@api_router.get("/auth/me", response_model=Dealer)
async def get_current_user(dealer: Dealer = Depends(get_current_dealer)):
    """Get current dealer info"""
    return dealer

# ============= PRODUCT ROUTES =============

@api_router.get("/products", response_model=List[Product])
async def get_products():
    """Get all products"""
    products = await db.products.find({}, {"_id": 0}).to_list(1000)
    
    for product in products:
        if isinstance(product.get('created_at'), str):
            product['created_at'] = datetime.fromisoformat(product['created_at'])
    
    return products

@api_router.get("/products/{product_id}", response_model=Product)
async def get_product(product_id: str):
    """Get product by ID"""
    product = await db.products.find_one({"id": product_id}, {"_id": 0})
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    if isinstance(product.get('created_at'), str):
        product['created_at'] = datetime.fromisoformat(product['created_at'])
    
    return Product(**product)

# ============= CART ROUTES =============

@api_router.get("/cart", response_model=List[CartItemWithProduct])
async def get_cart(dealer: Dealer = Depends(get_current_dealer)):
    """Get dealer's cart"""
    cart_items = await db.cart_items.find({"dealer_id": dealer.id}, {"_id": 0}).to_list(1000)
    
    result = []
    for item in cart_items:
        product = await db.products.find_one({"id": item["product_id"]}, {"_id": 0})
        if product:
            if isinstance(product.get('created_at'), str):
                product['created_at'] = datetime.fromisoformat(product['created_at'])
            product_obj = Product(**product)
            subtotal = product_obj.price * item["quantity"]
            result.append(CartItemWithProduct(
                id=item["id"],
                product=product_obj,
                quantity=item["quantity"],
                subtotal=subtotal
            ))
    
    return result

@api_router.post("/cart", response_model=CartItem)
async def add_to_cart(item_data: CartItemCreate, dealer: Dealer = Depends(get_current_dealer)):
    """Add item to cart"""
    # Check if product exists
    product = await db.products.find_one({"id": item_data.product_id})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Check if item already in cart
    existing = await db.cart_items.find_one({
        "dealer_id": dealer.id,
        "product_id": item_data.product_id
    })
    
    if existing:
        # Update quantity
        new_quantity = existing["quantity"] + item_data.quantity
        await db.cart_items.update_one(
            {"id": existing["id"]},
            {"$set": {"quantity": new_quantity}}
        )
        existing["quantity"] = new_quantity
        if isinstance(existing.get('created_at'), str):
            existing['created_at'] = datetime.fromisoformat(existing['created_at'])
        return CartItem(**existing)
    
    # Create new cart item
    cart_item = CartItem(
        dealer_id=dealer.id,
        product_id=item_data.product_id,
        quantity=item_data.quantity
    )
    
    doc = cart_item.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    
    await db.cart_items.insert_one(doc)
    return cart_item

@api_router.put("/cart/{item_id}")
async def update_cart_item(item_id: str, quantity: int, dealer: Dealer = Depends(get_current_dealer)):
    """Update cart item quantity"""
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be greater than 0")
    
    result = await db.cart_items.update_one(
        {"id": item_id, "dealer_id": dealer.id},
        {"$set": {"quantity": quantity}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Cart item not found")
    
    return {"message": "Cart updated successfully"}

@api_router.delete("/cart/{item_id}")
async def remove_from_cart(item_id: str, dealer: Dealer = Depends(get_current_dealer)):
    """Remove item from cart"""
    result = await db.cart_items.delete_one({"id": item_id, "dealer_id": dealer.id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Cart item not found")
    
    return {"message": "Item removed from cart"}

@api_router.delete("/cart")
async def clear_cart(dealer: Dealer = Depends(get_current_dealer)):
    """Clear entire cart"""
    await db.cart_items.delete_many({"dealer_id": dealer.id})
    return {"message": "Cart cleared successfully"}

# ============= ORDER ROUTES =============

@api_router.post("/orders", response_model=Order)
async def create_order(order_data: OrderCreate, dealer: Dealer = Depends(get_current_dealer)):
    """Create order from cart"""
    # Get cart items
    cart_items = await db.cart_items.find({"dealer_id": dealer.id}, {"_id": 0}).to_list(1000)
    
    if not cart_items:
        raise HTTPException(status_code=400, detail="Cart is empty")
    
    # Build order items
    order_items = []
    total_amount = 0.0
    
    for item in cart_items:
        product = await db.products.find_one({"id": item["product_id"]}, {"_id": 0})
        if product:
            subtotal = product["price"] * item["quantity"]
            order_items.append(OrderItem(
                product_id=product["id"],
                product_name=product["name"],
                quantity=item["quantity"],
                price=product["price"],
                subtotal=subtotal
            ))
            total_amount += subtotal
    
    # Check credit limit for account payment
    if order_data.payment_method == PaymentMethod.ACCOUNT:
        available_credit = dealer.credit_limit - dealer.outstanding_balance
        if total_amount > available_credit:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient credit. Available: ₹{available_credit:.2f}, Required: ₹{total_amount:.2f}"
            )
    
    # Create order
    order = Order(
        order_number=generate_order_number(),
        dealer_id=dealer.id,
        items=order_items,
        total_amount=total_amount,
        payment_method=order_data.payment_method,
        payment_status=PaymentStatus.PENDING if order_data.payment_method == PaymentMethod.COD else PaymentStatus.COMPLETED,
        delivery_address=order_data.delivery_address,
        notes=order_data.notes
    )
    
    doc = order.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    doc['updated_at'] = doc['updated_at'].isoformat()
    doc['items'] = [item.model_dump() for item in order_items]
    
    await db.orders.insert_one(doc)
    
    # Update outstanding balance for account payment
    if order_data.payment_method == PaymentMethod.ACCOUNT:
        new_balance = dealer.outstanding_balance + total_amount
        await db.dealers.update_one(
            {"id": dealer.id},
            {"$set": {"outstanding_balance": new_balance}}
        )
    
    # Clear cart
    await db.cart_items.delete_many({"dealer_id": dealer.id})
    
    return order

@api_router.get("/orders", response_model=List[Order])
async def get_orders(dealer: Dealer = Depends(get_current_dealer)):
    """Get dealer's orders"""
    orders = await db.orders.find({"dealer_id": dealer.id}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    
    for order in orders:
        if isinstance(order.get('created_at'), str):
            order['created_at'] = datetime.fromisoformat(order['created_at'])
        if isinstance(order.get('updated_at'), str):
            order['updated_at'] = datetime.fromisoformat(order['updated_at'])
    
    return orders

@api_router.get("/orders/{order_id}", response_model=Order)
async def get_order(order_id: str, dealer: Dealer = Depends(get_current_dealer)):
    """Get order details"""
    order = await db.orders.find_one({"id": order_id, "dealer_id": dealer.id}, {"_id": 0})
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if isinstance(order.get('created_at'), str):
        order['created_at'] = datetime.fromisoformat(order['created_at'])
    if isinstance(order.get('updated_at'), str):
        order['updated_at'] = datetime.fromisoformat(order['updated_at'])
    
    return Order(**order)

# ============= DASHBOARD ROUTES =============

@api_router.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats(dealer: Dealer = Depends(get_current_dealer)):
    """Get dashboard statistics"""
    # Get all orders
    orders = await db.orders.find({"dealer_id": dealer.id}, {"_id": 0}).to_list(1000)
    
    total_orders = len(orders)
    pending_orders = len([o for o in orders if o["order_status"] == OrderStatus.PENDING])
    delivered_orders = len([o for o in orders if o["order_status"] == OrderStatus.DELIVERED])
    total_spent = sum(o["total_amount"] for o in orders)
    
    credit_available = dealer.credit_limit - dealer.outstanding_balance
    
    return DashboardStats(
        total_orders=total_orders,
        pending_orders=pending_orders,
        delivered_orders=delivered_orders,
        total_spent=total_spent,
        credit_available=credit_available,
        outstanding_balance=dealer.outstanding_balance
    )

# ============= CHAT ROUTES =============

@api_router.post("/chat", response_model=ChatResponse)
async def chat(message: ChatMessage, dealer: Dealer = Depends(get_current_dealer)):
    """Chat with AI assistant"""
    try:
        # Get API key from environment
        api_key = os.environ.get('EMERGENT_LLM_KEY')
        
        # Get dealer's recent orders for context
        recent_orders = await db.orders.find(
            {"dealer_id": dealer.id}, 
            {"_id": 0}
        ).sort("created_at", -1).limit(5).to_list(5)
        
        # Get all products for context
        products = await db.products.find({}, {"_id": 0}).to_list(100)
        
        # Build context
        products_info = "\n".join([
            f"- {p['name']}: ₹{p['price']} per {p['packaging']} (Grade: {p['grade']}, Stock: {p['stock']})"
            for p in products
        ])
        
        orders_info = ""
        if recent_orders:
            orders_info = "Recent orders:\n" + "\n".join([
                f"- Order {o['order_number']}: ₹{o['total_amount']}, Status: {o['order_status']}"
                for o in recent_orders[:3]
            ])
        
        # Create system message with context
        system_message = f"""You are an AI assistant for HumSafar Cement, helping dealer {dealer.name} from {dealer.business_name}.

Available Products:
{products_info}

Dealer Information:
- Credit Limit: ₹{dealer.credit_limit}
- Outstanding Balance: ₹{dealer.outstanding_balance}
- Available Credit: ₹{dealer.credit_limit - dealer.outstanding_balance}

{orders_info}

Help the dealer with:
1. Product information and recommendations
2. Order status and history
3. Credit and payment information
4. General support and queries

Be helpful, professional, and provide accurate information based on the context above."""

        # Initialize chat with dealer-specific session
        llm_chat = LlmChat(
            api_key=api_key,
            session_id=f"dealer_{dealer.id}",
            system_message=system_message
        ).with_model("openai", "gpt-5.1")
        
        # Create user message
        user_msg = UserMessage(text=message.message)
        
        # Get response from AI
        ai_response = await llm_chat.send_message(user_msg)
        
        return ChatResponse(response=ai_response)
        
    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        return ChatResponse(response="I apologize, but I'm having trouble processing your request right now. Please try again later or contact support.")

# ============= SEED DATA ROUTE (Development only) =============

@api_router.post("/seed-data")
async def seed_data():
    """Seed database with sample products"""
    # Check if products already exist
    existing = await db.products.count_documents({})
    if existing > 0:
        return {"message": "Products already exist"}
    
    products = [
        {
            "id": str(uuid.uuid4()),
            "name": "OPC 43 Grade Cement",
            "description": "Ordinary Portland Cement 43 Grade - Ideal for all types of construction work including RCC work, plastering, and masonry.",
            "category": "OPC",
            "grade": "43",
            "packaging": "50kg bag",
            "price": 350.0,
            "stock": 5000,
            "image_url": "https://images.unsplash.com/photo-1590642916589-592bca10dfbf?w=400",
            "specifications": {
                "compressive_strength": "43 MPa",
                "setting_time": "30 min - 10 hours",
                "fineness": "225 m2/kg"
            },
            "created_at": datetime.now(timezone.utc).isoformat()
        },
        {
            "id": str(uuid.uuid4()),
            "name": "OPC 53 Grade Cement",
            "description": "Ordinary Portland Cement 53 Grade - High strength cement for high-rise buildings and heavy-duty construction.",
            "category": "OPC",
            "grade": "53",
            "packaging": "50kg bag",
            "price": 380.0,
            "stock": 4500,
            "image_url": "https://images.unsplash.com/photo-1590642916589-592bca10dfbf?w=400",
            "specifications": {
                "compressive_strength": "53 MPa",
                "setting_time": "30 min - 10 hours",
                "fineness": "225 m2/kg"
            },
            "created_at": datetime.now(timezone.utc).isoformat()
        },
        {
            "id": str(uuid.uuid4()),
            "name": "PPC Cement",
            "description": "Portland Pozzolana Cement - Eco-friendly cement with improved workability and lower heat of hydration.",
            "category": "PPC",
            "grade": "PPC",
            "packaging": "50kg bag",
            "price": 340.0,
            "stock": 6000,
            "image_url": "https://images.unsplash.com/photo-1590642916589-592bca10dfbf?w=400",
            "specifications": {
                "compressive_strength": "33 MPa (28 days)",
                "setting_time": "30 min - 10 hours",
                "fineness": "300 m2/kg"
            },
            "created_at": datetime.now(timezone.utc).isoformat()
        },
        {
            "id": str(uuid.uuid4()),
            "name": "PSC Cement",
            "description": "Portland Slag Cement - Durable cement with better resistance to chemicals and sulfates.",
            "category": "PSC",
            "grade": "PSC",
            "packaging": "50kg bag",
            "price": 345.0,
            "stock": 3500,
            "image_url": "https://images.unsplash.com/photo-1590642916589-592bca10dfbf?w=400",
            "specifications": {
                "compressive_strength": "33 MPa (28 days)",
                "setting_time": "30 min - 10 hours",
                "fineness": "325 m2/kg"
            },
            "created_at": datetime.now(timezone.utc).isoformat()
        },
        {
            "id": str(uuid.uuid4()),
            "name": "OPC 43 Grade (25kg)",
            "description": "Ordinary Portland Cement 43 Grade in smaller 25kg packaging for small projects.",
            "category": "OPC",
            "grade": "43",
            "packaging": "25kg bag",
            "price": 185.0,
            "stock": 3000,
            "image_url": "https://images.unsplash.com/photo-1590642916589-592bca10dfbf?w=400",
            "specifications": {
                "compressive_strength": "43 MPa",
                "setting_time": "30 min - 10 hours",
                "fineness": "225 m2/kg"
            },
            "created_at": datetime.now(timezone.utc).isoformat()
        },
        {
            "id": str(uuid.uuid4()),
            "name": "OPC 53 Grade (25kg)",
            "description": "Ordinary Portland Cement 53 Grade in smaller 25kg packaging.",
            "category": "OPC",
            "grade": "53",
            "packaging": "25kg bag",
            "price": 200.0,
            "stock": 2500,
            "image_url": "https://images.unsplash.com/photo-1590642916589-592bca10dfbf?w=400",
            "specifications": {
                "compressive_strength": "53 MPa",
                "setting_time": "30 min - 10 hours",
                "fineness": "225 m2/kg"
            },
            "created_at": datetime.now(timezone.utc).isoformat()
        }
    ]
    
    await db.products.insert_many(products)
    return {"message": f"{len(products)} products added successfully"}

# ============= ROOT ROUTES =============

@api_router.get("/")
async def root():
    return {"message": "Cement Dealer Management API"}

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
