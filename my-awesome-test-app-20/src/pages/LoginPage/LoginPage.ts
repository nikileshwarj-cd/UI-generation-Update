import { useState, useCallback } from 'react';

interface LoginPageState {
  email: string;
  password: string;
  error: string | null;
  isLoading: boolean;
}

export const useLoginPage = () => {
  const [state, setState] = useState<LoginPageState>({
    email: '',
    password: '',
    error: null,
    isLoading: false,
  });

  const validateEmail = (email: string): boolean => {
    const regex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
    return regex.test(email.trim());
  };

  const validatePassword = (password: string): boolean => {
    return password.trim().length >= 8;
  };

  const handleEmailChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setState(prev => ({ ...prev, email: e.target.value, error: null }));
  }, []);

  const handlePasswordChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setState(prev => ({ ...prev, password: e.target.value, error: null }));
  }, []);

  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    
    const trimmedEmail = state.email.trim();
    const trimmedPassword = state.password.trim();

    if (!trimmedEmail || !trimmedPassword) {
      setState(prev => ({ ...prev, error: 'Both fields must be non-empty before submission' }));
      return;
    }

    if (!validateEmail(trimmedEmail)) {
      setState(prev => ({ ...prev, error: 'Please enter a valid email address' }));
      return;
    }

    if (!validatePassword(trimmedPassword)) {
      setState(prev => ({ ...prev, error: 'Password must be at least 8 characters' }));
      return;
    }

    setState(prev => ({ ...prev, isLoading: true, error: null }));

    try {
      await new Promise(resolve => setTimeout(resolve, 1000));
      console.log('Login successful, redirecting to dashboard');
    } catch (err) {
      setState(prev => ({ ...prev, error: 'Authentication failed. Please try again.', isLoading: false }));
    }
  }, [state.email, state.password]);

  return {
    state,
    handleEmailChange,
    handlePasswordChange,
    handleSubmit,
  };
};