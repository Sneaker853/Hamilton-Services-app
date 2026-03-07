# Portfolio Optimizer Web Application

Professional portfolio optimization engine with FastAPI backend and React.js frontend.

## 🚀 Quick Start

**Servers Running:**
- Frontend: http://localhost:3000
- Backend: http://localhost:8000/api
- Market Data: http://localhost:3000/market-data

## 📋 Current Status

### ✅ Completed
- Professional dark theme with teal accents (Hamilton Services)
- Responsive dashboard with sidebar navigation
- Portfolio generator with multiple personas
- Portfolio builder with optimization tools
- Market Data page with price charts

## Project Structure

```
portfolio_web/
├── backend/              # FastAPI REST API
│   ├── main.py          # Application entry point (UPDATED)
│   └── requirements.txt  # Python dependencies
├── frontend/            # React.js web UI
│   ├── src/
│   │   ├── pages/
│   │   │   ├── MarketData.js      # Stock exploration (NEW)
│   │   │   ├── Dashboard.js
│   │   │   ├── PortfolioGenerator.js
│   │   │   └── ...
│   │   ├── App.js
│   │   ├── index.js
│   │   └── index.css    # Updated typography
│   ├── public/
│   ├── package.json
│   └── .env
```

## Tech Stack

**Backend:**
- FastAPI 0.109.0
- Python 3.11
- PostgreSQL
- Pandas, NumPy

**Frontend:**
- React.js 18
- Custom CSS + CSS variables
- Recharts (charts)
- Axios (API calls)

**Deployment:**
- Docker
- Docker Compose

## Getting Started

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL 15+
- Docker (optional)

### Local Development

**1. Backend Setup**

```bash
cd backend
python -m venv venv
source venv/Scripts/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Backend runs on `http://localhost:8000`

**2. Frontend Setup**

```bash
cd frontend
npm install
npm start
```

Frontend runs on `http://localhost:3000`

**3. Database Setup**

Make sure PostgreSQL is running with two databases:
- `portfolio_db` (stocks, prices, fundamentals)
- `market_data` (Fama-French factors)

## API Endpoints

### Health & Info
- `GET /health` - Health check
- `GET /api/personas` - Available personas
- `GET /api/stocks/summary` - Market summary

### Portfolio Generation
- `POST /api/portfolio/generate` - Generate optimized portfolio
- `POST /api/portfolio/analyze` - Analyze portfolio

### Stock Screening
- `GET /api/stocks/screen` - Screen and rank stocks
- `GET /api/sectors` - Available sectors

## Docker Deployment

### Start All Services

```bash
cd docker
docker-compose up -d
```

This will start:
- PostgreSQL (5432)
- Market Data DB (5433)
- FastAPI Backend (8000)
- React Frontend (3000)

### View Logs

```bash
docker-compose logs -f backend
docker-compose logs -f frontend
```

### Stop Services

```bash
docker-compose down
```

## Configuration

### Backend (.env)
```
DATABASE_URL=postgresql://user:password@localhost:5432/portfolio_db
MARKET_DATA_URL=postgresql://user:password@localhost:5432/market_data
```

### Frontend (.env)
```
REACT_APP_API_URL=http://localhost:8000/api
```

## API Documentation

Once backend is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Development

### Adding New Endpoints

1. Add Pydantic model in `backend/main.py`
2. Create endpoint function with `@app.get/post/put/delete`
3. Call existing `screener` or `portfolio_builder` services
4. Return JSON response

### Adding New React Pages

1. Create component in `frontend/src/pages/`
2. Import in `frontend/src/App.js`
3. Add route in Routes section
4. Add navigation link in navbar

## Performance Tips

- Backend caches Fama-French factors (no repeated DB queries)
- Portfolio generation takes ~5-10 seconds for 20+ stocks
- Stock screening is real-time with <1s response
- Frontend caching optimized with React hooks

## Future Enhancements

- [ ] User authentication & portfolios saved
- [ ] Advanced analytics & backtesting
- [ ] Real-time market data
- [ ] Mobile app (React Native)
- [ ] WebSocket for live updates
- [ ] Export to Excel/PDF
- [ ] Portfolio comparison

## Troubleshooting

**Backend won't start:**
- Check PostgreSQL is running
- Verify database credentials
- Run `python pre_webapp_validation.py` from portfolio_app directory

**Frontend won't connect to backend:**
- Ensure backend is running on 8000
- Check CORS is enabled
- Verify `REACT_APP_API_URL` in .env

**Database errors:**
- Check connection strings
- Verify credentials
- Ensure databases exist

## License

Proprietary - Portfolio Optimization System

## Support

For issues or questions, refer to the API documentation at `/docs` when backend is running.
