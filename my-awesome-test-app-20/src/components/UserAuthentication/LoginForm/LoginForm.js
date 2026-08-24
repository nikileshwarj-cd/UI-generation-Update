import { useState } from 'react';

export const useLoginForm = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const handleEmailChange = (e) => setEmail(e.target.value);
  const handlePasswordChange = (e) => setPassword(e.target.value);
  const handleSubmit = () => {
    // TO DO: implement login logic
    console.log('Login form submitted');
  };
  return { email, password, handleEmailChange, handlePasswordChange, handleSubmit };
};