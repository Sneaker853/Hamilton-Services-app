import React, { createContext, useContext, useState, useCallback } from 'react';
import en from '../translations/en';
import fr from '../translations/fr';
import frLiterals from '../translations/frLiterals';

const TRANSLATIONS = { en, fr };

const LanguageContext = createContext({
  lang: 'en',
  setLang: () => {},
  t: (key) => key,
  tt: (text) => text,
});

export const LanguageProvider = ({ children }) => {
  const [lang, setLang] = useState(() => {
    try {
      return localStorage.getItem('preferredLang') || 'en';
    } catch {
      return 'en';
    }
  });

  const changeLang = useCallback((newLang) => {
    setLang(newLang);
    try {
      localStorage.setItem('preferredLang', newLang);
    } catch {}
  }, []);

  const t = useCallback((key, fallback) => {
    const dict = TRANSLATIONS[lang] || en;
    return dict[key] ?? fallback ?? key;
  }, [lang]);

  const tt = useCallback((text) => {
    if (lang !== 'fr') return text;
    return frLiterals[text] || text;
  }, [lang]);

  return (
    <LanguageContext.Provider value={{ lang, setLang: changeLang, t, tt }}>
      {children}
    </LanguageContext.Provider>
  );
};

export const useLanguage = () => useContext(LanguageContext);

export default LanguageContext;
