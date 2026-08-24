import React from 'react';
import './App.css';
import LoginPage from './pages/LoginPage/LoginPage';

const App: React.FC = () => {
  return (
    <div className="app-container">
      <LoginPage />
    </div>
  );
};

export default App;