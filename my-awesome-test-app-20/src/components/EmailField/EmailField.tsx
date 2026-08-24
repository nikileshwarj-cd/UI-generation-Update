import React from 'react';
import './EmailField.css';

const EmailField: React.FC = () => {
  return (
    <input
      type="email"
      placeholder="Email"
      className="email-field"
    />
  );
};

export default EmailField;