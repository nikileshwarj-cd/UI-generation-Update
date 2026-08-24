import React from 'react';
import { useUserAuthenticationPage } from './UserAuthentication';
import './UserAuthentication.css';

const UserAuthentication: React.FC = () => {
  const { email, password, error, isLoading, handleEmailChange, handlePasswordChange, handleSubmit } = useUserAuthenticationPage();

  return (
    <div className="w-full max-w-md p-8 bg-white rounded-xl shadow-lg">
      <h1 className="text-2xl font-bold text-center text-slate-800 mb-6">Sign In</h1>
      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        <div>
          <label htmlFor="email" className="block text-sm font-medium text-slate-700 mb-1">Email</label>
          <input
            id="email"
            type="email"
            value={email}
            onChange={handleEmailChange}
            placeholder="Enter your email"
            className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
            required
            aria-invalid={!!error && error.includes('email')}
            aria-describedby={error && error.includes('email') ? 'email-error' : undefined}
          />
        </div>
        <div>
          <label htmlFor="password" className="block text-sm font-medium text-slate-700 mb-1">Password</label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={handlePasswordChange}
            placeholder="Enter your password"
            className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
            required
            aria-invalid={!!error && error.includes('password')}
            aria-describedby={error && error.includes('password') ? 'password-error' : undefined}
          />
        </div>
        {error && (
          <div className="text-red-500 text-sm font-medium" role="alert" id="form-error">
            {error}
          </div>
        )}
        <button
          type="submit"
          disabled={isLoading}
          className="w-full py-2 px-4 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isLoading ? 'Logging in...' : 'Submit'}
        </button>
        <p className="text-center text-sm text-slate-500 mt-4">
          Need an account? <a href="#" className="text-blue-600 hover:underline">Login</a>
        </p>
      </form>
    </div>
  );
};

export default UserAuthentication;