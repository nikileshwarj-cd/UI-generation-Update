import React from 'react';
import LoginForm from './LoginForm/LoginForm';
import './MainContent.css';

const MainContent: React.FC = () => {
  return (
    <main className="main-content">
      <LoginForm />
    </main>
  );
};

export default MainContent;