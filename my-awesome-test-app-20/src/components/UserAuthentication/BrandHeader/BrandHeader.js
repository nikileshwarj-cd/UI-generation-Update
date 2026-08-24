import { useState } from 'react';

export const useBrandHeader = () => {
  const welcomeText = 'Welcome Back';
  const subtitleText = 'Enter your credentials to continue';
  return { welcomeText, subtitleText };
};