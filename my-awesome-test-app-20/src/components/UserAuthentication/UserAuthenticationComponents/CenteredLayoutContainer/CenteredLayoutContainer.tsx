import React from 'react';
import './CenteredLayoutContainer.css';

interface CenteredLayoutContainerProps {
  children: React.ReactNode;
}

export const CenteredLayoutContainer: React.FC<CenteredLayoutContainerProps> = ({ children }) => {
  return (
    <div className="centered-layout-container">
      {children}
    </div>
  );
};