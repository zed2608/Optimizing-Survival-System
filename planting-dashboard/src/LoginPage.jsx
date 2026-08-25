import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

// ---------------------------------------------------------------------------
// LoginPage
// Matches the visual language already used in App.jsx:
//   - navy header (#1a365d)
//   - blue action buttons (#3182ce)
//   - light grey page background (#f4f6f8)
//   - white cards with soft shadows and rounded corners
//
// NOTE ON AUTH: There is no auth endpoint on the FastAPI backend yet
// (main.py currently only exposes /api/optimize-planting). To keep this
// screen usable right now, a "demo" login is used: any non-empty
// username/password combination succeeds, and we store a flag in
// localStorage so ProtectedRoute (see main.jsx) knows the user is signed in.
//
// When a real backend login endpoint exists, replace the body of
// handleSubmit with an axios.post('http://localhost:8000/api/login', ...)
// call and store the returned token instead of the "demo-token" string.
// ---------------------------------------------------------------------------

function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (username.trim() !== 'admin' || password.trim() !== 'admin123') {
      setError('Invalid username or password.');
      return;
    }

    setSubmitting(true);

    await new Promise((resolve) => setTimeout(resolve, 400));
    localStorage.setItem('authToken', 'demo-token');
    localStorage.setItem('username', 'admin');

    setSubmitting(false);
    navigate('/');
  };

  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        height: '100vh',
        width: '100vw',
        fontFamily: 'sans-serif',
        backgroundColor: '#f4f6f8',
        margin: 0,
      }}
    >
      <div
        style={{
          width: '380px',
          backgroundColor: 'white',
          borderRadius: '8px',
          boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
          overflow: 'hidden',
        }}
      >
        <div style={{ padding: '25px 30px', backgroundColor: '#1a365d', color: 'white' }}>
          <h2 style={{ margin: 0, fontSize: '1.4rem', fontWeight: 'bold' }}>
            San Mateo LGU
          </h2>
          <p style={{ margin: '5px 0 0 0', fontSize: '0.9rem', color: '#a0aec0' }}>
            Greening Optimization Dashboard
          </p>
        </div>

        <form onSubmit={handleSubmit} style={{ padding: '30px' }}>
          <h3 style={{ marginTop: 0, marginBottom: '20px', fontSize: '1.1rem', color: '#2d3748' }}>
            Sign in to continue
          </h3>

          <label
            htmlFor="username"
            style={{ display: 'block', fontSize: '0.85rem', color: '#4a5568', marginBottom: '6px' }}
          >
            Username
          </label>
          <input
            id="username"
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="e.g. lgu.planner"
            style={inputStyle}
            autoComplete="username"
          />

          <label
            htmlFor="password"
            style={{ display: 'block', fontSize: '0.85rem', color: '#4a5568', margin: '16px 0 6px' }}
          >
            Password
          </label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            style={inputStyle}
            autoComplete="current-password"
          />

          {error && (
            <p style={{ color: '#c53030', fontSize: '0.85rem', marginTop: '12px', marginBottom: 0 }}>
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={submitting}
            style={{
              width: '100%',
              padding: '14px',
              marginTop: '24px',
              backgroundColor: submitting ? '#a0c4e4' : '#3182ce',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              fontWeight: 'bold',
              fontSize: '1rem',
              cursor: submitting ? 'not-allowed' : 'pointer',
              boxShadow: '0 4px 6px rgba(49, 130, 206, 0.2)',
            }}
          >
            {submitting ? 'Signing in…' : 'Sign In'}
          </button>

          <p style={{ fontSize: '0.75rem', color: '#a0aec0', marginTop: '16px', textAlign: 'center' }}>
            Demo account: admin / admin123
          </p>
        </form>
      </div>
    </div>
  );
}

const inputStyle = {
  width: '100%',
  padding: '10px 12px',
  fontSize: '0.95rem',
  border: '1px solid #e2e8f0',
  borderRadius: '6px',
  boxSizing: 'border-box',
  color: '#2d3748',
  outline: 'none',
};

export default LoginPage;
