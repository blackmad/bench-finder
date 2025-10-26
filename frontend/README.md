# Bench Finder Frontend

A React + TypeScript + Vite frontend for the Bench Finder application, providing an interactive web interface for finding and visualizing benches.

## Features

- 🗺️ **Interactive Map**: View bench locations on an interactive map
- 🔍 **Search Interface**: Search for benches by location with custom radius
- 📊 **Data Visualization**: Display bench detection results with confidence scores
- 🖼️ **Image Gallery**: View Street View and Mapillary images of detected benches
- 📱 **Responsive Design**: Works on desktop and mobile devices
- ⚡ **Fast Development**: Hot module replacement with Vite

## Tech Stack

- **React 18** - Modern React with hooks and concurrent features
- **TypeScript** - Type-safe JavaScript development
- **Vite** - Fast build tool and development server
- **Tailwind CSS** - Utility-first CSS framework
- **React Query** - Data fetching and caching
- **React Router** - Client-side routing

## Development

### Prerequisites

- Node.js 18+
- npm or yarn

### Setup

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

### Available Scripts

- `npm run dev` - Start development server with HMR
- `npm run build` - Build for production
- `npm run preview` - Preview production build
- `npm run lint` - Run ESLint
- `npm run type-check` - Run TypeScript type checking

## API Integration

The frontend connects to the Bench Finder FastAPI backend running on port 8866. Key API endpoints:

- `GET /api/benches` - List benches with pagination and filtering
- `GET /api/benches/bbox` - Search benches within bounding box
- `GET /api/benches/random` - Get random bench for testing
- `GET /images/{filename}` - Serve bench images
- `POST /api/mapillary/search` - Search Mapillary for benches

## Project Structure

```
frontend/
├── src/
│   ├── components/     # Reusable React components
│   ├── pages/         # Page components
│   ├── hooks/         # Custom React hooks
│   ├── services/      # API service functions
│   ├── types/         # TypeScript type definitions
│   ├── utils/         # Utility functions
│   └── App.tsx        # Main application component
├── public/            # Static assets
├── package.json       # Dependencies and scripts
├── vite.config.ts     # Vite configuration
├── tsconfig.json      # TypeScript configuration
└── tailwind.config.js # Tailwind CSS configuration
```

## Configuration

The frontend can be configured via environment variables:

```bash
# API base URL (default: http://localhost:8866)
VITE_API_BASE_URL=http://localhost:8866

# Map API key (if using external map service)
VITE_MAP_API_KEY=your_map_api_key
```

## Building and Deployment

### Production Build

```bash
npm run build
```

This creates a `dist/` directory with optimized production assets.

### Deployment

The built files can be served by any static file server or CDN. For example:

```bash
# Serve with Python
cd dist && python -m http.server 8000

# Serve with Node.js
npx serve dist

# Deploy to Vercel, Netlify, etc.
```

## Development Workflow

1. **Start Backend**: Ensure the FastAPI server is running on port 8866
2. **Start Frontend**: Run `npm run dev` to start the development server
3. **Open Browser**: Navigate to http://localhost:5173
4. **Make Changes**: Edit files and see changes instantly with HMR

## Contributing

1. Follow the existing code style and patterns
2. Add TypeScript types for all new components and functions
3. Write tests for new features
4. Update documentation as needed
5. Run linting and type checking before committing

## Troubleshooting

### Common Issues

**API Connection Errors**
- Ensure the FastAPI backend is running on port 8866
- Check CORS settings in the backend
- Verify API endpoints are accessible

**Build Errors**
- Clear node_modules and reinstall: `rm -rf node_modules && npm install`
- Check TypeScript errors: `npm run type-check`
- Verify all dependencies are installed

**Development Server Issues**
- Try a different port: `npm run dev -- --port 3000`
- Clear Vite cache: `rm -rf node_modules/.vite`
- Check for port conflicts
