import { useState } from 'react';

const useLoginForm = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    // Authenticate user credentials
  };

  return { email, setEmail, password, setPassword, handleSubmit };
};

export default useLoginForm;