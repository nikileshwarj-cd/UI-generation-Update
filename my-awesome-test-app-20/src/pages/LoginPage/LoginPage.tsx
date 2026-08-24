import React from 'react';
import { useLoginPage } from './LoginPage';
import './LoginPage.css';

const LoginPage: React.FC = () => {
  const { state, handleEmailChange, handlePasswordChange, handleSubmit } = useLoginPage();

  return (
    <div className="login-page-container">
      <div className="login-card">
        <h1 className="login-heading">Sign In</h1>
        
        {state.error && (
          <p className="error-message">{state.error}</p>
        )}
        
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="email" className="form-label">Email</label>
            <input
              id="email"
              type="email"
              className="form-input"
              placeholder="Enter your email"
              value={state.email}
              onChange={handleEmailChange}
              autoComplete="email"
            />
          </div>
          
          <div className="form-group">
            <label htmlFor="password" className="form-label">Password</label>
            <input
              id="password"
              type="password"
              className="form-input"
              placeholder="Enter your password"
              value={state.password}
              onChange={handlePasswordChange}
              autoComplete="current-password"
            />
          </div>
          
          <button
            type="submit"
            className="submit-button"
            disabled={state.isLoading}
          >
            {state.isLoading ? 'Signing in...' : 'Submit'}
          </button>
        </form>
      </div>
    </div>
  );
};

export default LoginPage;