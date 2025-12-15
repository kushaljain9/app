# HumSafar Cement - Dealer Management System

## Overview
A comprehensive dealer/retailer management application for cement products, similar to M P Birla Humsafar app, with full e-commerce functionality, credit management, and AI-powered chatbot support.

## Features Implemented

### 🔐 Authentication
- **OTP-based Login**: Secure phone number authentication with OTP
- **Dealer Registration**: Complete registration with business details
- **Session Management**: Token-based authentication

### 📦 Product Management
- **Product Catalog**: Browse all available cement products
- **Product Details**: View specifications, pricing, and stock
- **Categories**: OPC 43, OPC 53, PPC, PSC grades
- **Multiple Packaging**: 25kg and 50kg options

### 🛒 Shopping Cart
- **Add to Cart**: Add products with quantity
- **Update Quantity**: Increase/decrease quantities
- **Remove Items**: Delete individual items or clear entire cart
- **Real-time Total**: Calculate total amount dynamically

### 💳 Checkout & Payment
- **COD (Cash on Delivery)**: Pay when order is delivered
- **Account Payment**: Use credit limit for payment
- **Credit Management**: Track credit limit and outstanding balance
- **Delivery Address**: Specify delivery location
- **Order Notes**: Add special instructions

### 📋 Order Management
- **Order History**: View all past orders
- **Order Tracking**: Track order status (Pending → Confirmed → Processing → Shipped → Delivered)
- **Order Details**: View complete order information
- **Payment Status**: Track payment completion

### 📊 Dashboard
- **Statistics**: Total orders, pending orders, delivered orders, total spent
- **Credit Information**: Credit limit, outstanding balance, available credit
- **Quick Actions**: Quick links to browse products, view orders, and cart

### 👤 Profile Management
- **Personal Information**: Name, phone, email, business name, address
- **GST Details**: GST number if available
- **Credit Summary**: Complete credit information overview
- **Account History**: Member since date

### 💬 AI Chatbot
- **Intelligent Assistant**: Powered by OpenAI GPT-5.1
- **Context-Aware**: Knows about products, orders, and dealer information
- **24/7 Support**: Always available for queries
- **Floating Widget**: Accessible from all pages

## Technology Stack

### Backend
- **Framework**: FastAPI (Python)
- **Database**: MongoDB with Motor (async driver)
- **Authentication**: Token-based with OTP
- **AI Integration**: emergentintegrations library with OpenAI GPT-5.1
- **Environment**: Python with async/await

### Frontend
- **Framework**: React 19
- **Routing**: React Router v7
- **Styling**: Tailwind CSS + Radix UI components
- **Icons**: Lucide React
- **HTTP Client**: Axios
- **State Management**: React Context API

## Database Collections

### dealers
- Dealer/user information
- Credit limits and outstanding balance
- Authentication tokens

### products
- Cement product catalog
- Pricing, stock, specifications

### cart_items
- Shopping cart items per dealer
- Product references and quantities

### orders
- Order history and details
- Order items, payment info, delivery address
- Status tracking

## API Endpoints

### Authentication
- `POST /api/auth/register` - Register new dealer
- `POST /api/auth/send-otp` - Send OTP to phone
- `POST /api/auth/verify-otp` - Verify OTP and login
- `GET /api/auth/me` - Get current user info

### Products
- `GET /api/products` - List all products
- `GET /api/products/{id}` - Get product details

### Cart
- `GET /api/cart` - Get cart items
- `POST /api/cart` - Add item to cart
- `PUT /api/cart/{id}` - Update cart item quantity
- `DELETE /api/cart/{id}` - Remove item from cart
- `DELETE /api/cart` - Clear entire cart

### Orders
- `POST /api/orders` - Create order from cart
- `GET /api/orders` - List dealer's orders
- `GET /api/orders/{id}` - Get order details

### Dashboard
- `GET /api/dashboard/stats` - Get dashboard statistics

### Chatbot
- `POST /api/chat` - Send message to AI chatbot

### Development
- `POST /api/seed-data` - Seed database with sample products

## Setup Instructions

### Prerequisites
- Python 3.8+
- Node.js 16+
- MongoDB
- Yarn package manager

### Backend Setup
```bash
cd /app/backend
pip install -r requirements.txt
# Environment variables are already configured in .env
```

### Frontend Setup
```bash
cd /app/frontend
yarn install
```

### Running the Application
Both services are managed by supervisor:
```bash
# Restart backend
sudo supervisorctl restart backend

# Restart frontend
sudo supervisorctl restart frontend

# Check status
sudo supervisorctl status
```

### Seeding Data
```bash
curl -X POST http://localhost:8001/api/seed-data
```

## Default Test Account
After registration, use any phone number to register and receive OTP for login.

Example test dealer:
- Phone: 9876543210
- Name: Test Dealer
- Business: Test Cement Trading
- Email: dealer@test.com
- GST: 27AAPFU0939F1ZV
- Credit Limit: ₹100,000 (default)

## Credit Management
- Each dealer has a default credit limit of ₹100,000
- Orders using "Account" payment method deduct from available credit
- Outstanding balance tracks unpaid account orders
- Available credit = Credit Limit - Outstanding Balance

## AI Chatbot Features
The chatbot is powered by OpenAI GPT-5.1 and has access to:
- All product information
- Dealer's recent orders
- Credit and payment information
- Can answer queries about products, orders, and account

Uses Emergent LLM Key (universal key) for AI integration.

## URLs
- Backend API: http://localhost:8001
- Frontend: http://localhost:3000
- Production: Uses REACT_APP_BACKEND_URL from frontend/.env

## Sample Products
1. OPC 43 Grade Cement (50kg) - ₹350
2. OPC 53 Grade Cement (50kg) - ₹380
3. PPC Cement (50kg) - ₹340
4. PSC Cement (50kg) - ₹345
5. OPC 43 Grade (25kg) - ₹185
6. OPC 53 Grade (25kg) - ₹200

## Order Status Flow
1. **Pending**: Order placed, awaiting confirmation
2. **Confirmed**: Order confirmed by system
3. **Processing**: Order being prepared
4. **Shipped**: Order dispatched for delivery
5. **Delivered**: Order successfully delivered
6. **Cancelled**: Order cancelled

## Payment Methods
1. **COD (Cash on Delivery)**: Pay when receiving the order
2. **Account Payment**: Use credit limit, adds to outstanding balance

## Mobile Responsive
The application is fully responsive and works seamlessly on:
- Desktop (1920x1080+)
- Tablet (768x1024)
- Mobile (375x667+)

## Testing
All interactive elements have `data-testid` attributes for automated testing:
- Navigation links: `nav-dashboard`, `nav-products`, `nav-orders`, `nav-cart`, `nav-profile`
- Forms: `login-phone`, `login-otp`, `register-*` fields
- Buttons: `send-otp-button`, `verify-otp-button`, `place-order-button`, etc.
- Stats: `stat-total-orders`, `stat-pending-orders`, etc.

## Support
For any issues or queries, use the AI chatbot available on all pages or contact support.

---

**Built with ❤️ for cement dealers and retailers**
