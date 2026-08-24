import { useState } from 'react';

const useMainContent = () => {
  const [loginForm, setLoginForm] = useState({ email: '', password: '' });

  return { loginForm, setLoginForm };
};

export default useMainContent;