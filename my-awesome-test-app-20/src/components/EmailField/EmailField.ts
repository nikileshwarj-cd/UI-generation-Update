import { useState } from 'react';

const useEmailField = () => {
  const [email, setEmail] = useState('');

  const handleEmailChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setEmail(event.target.value);
  };

  return { email, handleEmailChange };
};

export default useEmailField;