import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { Toaster } from "sonner";
import { App } from "./App";
import { AuthProvider } from "./auth/AuthContext";
import { ConfirmProvider } from "./components/ConfirmProvider";
import { LanguageProvider } from "./i18n/LanguageContext";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <LanguageProvider>
      <AuthProvider>
        <BrowserRouter>
          <ConfirmProvider>
            <App />
            {/* richColors gives success/warning/error toasts their own
                green/yellow/red background + icon instead of one flat
                color for every toast type - a fixed toastOptions.style
                here previously overrode that distinction entirely. */}
            <Toaster theme="dark" position="bottom-right" richColors />
          </ConfirmProvider>
        </BrowserRouter>
      </AuthProvider>
    </LanguageProvider>
  </React.StrictMode>,
);
