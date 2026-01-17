import MapView from './components/MapView';
import './styles/global.css';

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_ACCESS_TOKEN;

function App() {
  if (!MAPBOX_TOKEN) {
    return (
      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center', 
        height: '100vh',
        flexDirection: 'column',
        gap: '16px'
      }}>
        <h1>PharmAccess Explorer</h1>
        <p style={{ color: '#d32f2f' }}>
          Error: VITE_MAPBOX_ACCESS_TOKEN environment variable is not set.
        </p>
        <p style={{ color: '#666', fontSize: '14px' }}>
          Please create a <code>.env</code> file with:<br/>
          <code>VITE_MAPBOX_ACCESS_TOKEN=your_token_here</code>
        </p>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', width: '100vw' }}>
      <header style={{
        padding: '16px 24px',
        backgroundColor: '#1a1a2e', // Dusky dark blue-gray background
        borderBottom: '1px solid #2d2d44',
        boxShadow: '0 2px 4px rgba(0,0,0,0.3)',
        zIndex: 1000,
        flexShrink: 0
      }}>
        <h1 style={{ 
          margin: 0, 
          fontSize: '24px', 
          fontWeight: 600,
          color: '#e0e0e0' // Light text for dark background
        }}>
          PharmAccess Explorer
        </h1>
        <p style={{ 
          margin: '4px 0 0 0', 
          fontSize: '14px', 
          color: '#b0b0b0' // Lighter gray for subtitle
        }}>
          Mapping pharmacy deserts and supply-chain connectivity across the United States
        </p>
      </header>
      <div style={{ flex: 1, position: 'relative', minHeight: 0, width: '100%' }}>
        <MapView mapboxToken={MAPBOX_TOKEN} />
      </div>
    </div>
  );
}

export default App;

