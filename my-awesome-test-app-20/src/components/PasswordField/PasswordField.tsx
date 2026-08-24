import React from 'react';
import './PasswordField.css';

const PasswordField: React.FC = () => {
  return (
    <input
      type="password"
      placeholder="Password"
      className="password-field"
    />
  );
};

export default PasswordField;