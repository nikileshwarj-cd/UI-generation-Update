import { useState } from 'react';

const useSubmitButton = () => {
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = () => {
    setIsSubmitting(true);
    // Authenticate user credentials
  };

  return { isSubmitting, handleSubmit };
};

export default useSubmitButton;