import { useState } from 'react';

const usePasswordField = () => {
  const [password, setPassword] = useState('');

  const handlePasswordChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setPassword(event.target.value);
  };

  return { password, handlePasswordChange };
};

export default usePasswordField;