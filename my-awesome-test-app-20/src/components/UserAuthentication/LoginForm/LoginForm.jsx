import React, { useState } from 'react';
import './LoginForm.css';
import { useLoginForm } from './LoginForm.js';

const LoginForm = () => {
  const { email, password, handleEmailChange, handlePasswordChange, handleSubmit } = useLoginForm();
  return (
    <div className="login-form">
      <h2>Email Address</h2>
      <input type="email" value={email} onChange={handleEmailChange} placeholder="m@example.com" />
      <h2>Password</h2>
      <input type="password" value={password} onChange={handlePasswordChange} placeholder="********" />
      <button onClick={handleSubmit}>Sign In</button>
      <div dangerouslySetInnerHTML={{ __html: '<svg width='20' height='20' viewBox='0 0 24 24' fill='none' stroke='#64748B' stroke-width='2'><path d='M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z'/><circle cx='12' cy='12' r='3'/></svg>' }} />
    </div>
  );
};

export default LoginForm;