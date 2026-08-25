import { Navigate } from 'react-router-dom';
import NavBar from './NavBar.jsx';

// Wraps a page and redirects to /login if no authToken is stored.
// Renders the NavBar above the protected page so users can navigate
// between Dashboard and History once signed in.

function ProtectedRoute({ children }) {
  const isLoggedIn = Boolean(localStorage.getItem('authToken'));

  if (!isLoggedIn) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <NavBar />
      <div style={{ flex: 1, minHeight: 0 }}>{children}</div>
    </div>
  );
}

export default ProtectedRoute;
