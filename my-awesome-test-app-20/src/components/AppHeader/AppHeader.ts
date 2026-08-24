import { useState } from 'react';

const useAppHeader = () => {
  const [title, setTitle] = useState('Login Form');

  return { title };
};

export default useAppHeader;