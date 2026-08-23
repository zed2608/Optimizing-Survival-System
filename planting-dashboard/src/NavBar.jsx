import { Link, useNavigate, useLocation } from 'react-router-dom';

// Slim top nav bar. Sits above whatever page is active.
// Matches the navy/blue palette used everywhere else in the app.

function NavBar() {
  const navigate = useNavigate();
  const location = useLocation();
  const username = localStorage.getItem('username');

  const handleLogout = () => {
    localStorage.removeItem('authToken');
    localStorage.removeItem('username');
    navigate('/login');
  };

  const linkStyle = (path) => ({
    color: location.pathname === path ? 'white' : '#a0aec0',
    fontWeight: location.pathname === path ? 'bold' : 'normal',
    textDecoration: 'none',
    fontSize: '0.9rem',
  });

  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '10px 24px',
        backgroundColor: '#12294a',
        fontFamily: 'sans-serif',
      }}
    >
      <div style={{ display: 'flex', gap: '24px' }}>
        <Link to="/" style={linkStyle('/')}>
          Dashboard
        </Link>
        <Link to="/history" style={linkStyle('/history')}>
          History &amp; Logs
        </Link>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        {username && <span style={{ color: '#a0aec0', fontSize: '0.85rem' }}>{username}</span>}
        <button
          onClick={handleLogout}
          style={{
            padding: '6px 14px',
            backgroundColor: 'transparent',
            border: '1px solid #4a5568',
            borderRadius: '6px',
            color: '#e2e8f0',
            fontSize: '0.8rem',
            cursor: 'pointer',
          }}
        >
          Log Out
        </button>
      </div>
    </div>
  );
}

export default NavBar;
