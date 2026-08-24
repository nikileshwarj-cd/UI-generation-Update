import React from 'react';
import './BrandHeader.css';
import { useBrandHeader } from './BrandHeader.js';

const BrandHeader = () => {
  const { welcomeText, subtitleText } = useBrandHeader();
  return (
    <div className="brand-header">
      <h1>{welcomeText}</h1>
      <p>{subtitleText}</p>
      <div dangerouslySetInnerHTML={{ __html: '<svg width='40' height='40' viewBox='0 0 24 24' fill='none' stroke='#3B82F6' stroke-width='2'><path d='M12 2L2 7l10 5 10-5-10-5z'/><path d='M2 17l10 5 10-5'/><path d='M2 12l10 5 10-5'/></svg>' }} />
    </div>
  );
};

export default BrandHeader;