import React from 'react';
import EmailField from './EmailField/EmailField';
import PasswordField from './PasswordField/PasswordField';
import SubmitButton from './SubmitButton/SubmitButton';
import './LoginForm.css';

const LoginForm: React.FC = () => {
  return (
    <form className="login-form">
      <EmailField />
      <PasswordField />
      <SubmitButton />
    </form>
  );
};

export default LoginForm;