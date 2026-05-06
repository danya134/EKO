import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { ChakraProvider, extendTheme } from '@chakra-ui/react'
import './index.css'
import App from './App.jsx'

const theme = extendTheme({
  styles: {
    global: {
      body: {
        bg: '#f4f1ec',
        color: '#1f2933',
        fontFamily: 'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      },
      '::selection': {
        bg: '#d7c6a3',
        color: '#111827',
      },
    },
  },
  fonts: {
    heading: 'Georgia, "Times New Roman", serif',
    body: 'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
  },
  components: {
    Button: {
      baseStyle: {
        borderRadius: '12px',
        fontWeight: '700',
      },
    },
    Card: {
      baseStyle: {
        container: {
          borderRadius: '22px',
          borderColor: '#ded6c8',
          boxShadow: '0 18px 45px rgba(31, 41, 51, 0.08)',
        },
      },
    },
    FormLabel: {
      baseStyle: {
        color: '#3f4652',
        fontSize: 'sm',
        fontWeight: '700',
        letterSpacing: '0.01em',
      },
    },
    Input: {
      defaultProps: {
        focusBorderColor: '#2f4f6f',
      },
    },
    Select: {
      defaultProps: {
        focusBorderColor: '#2f4f6f',
      },
    },
    Textarea: {
      defaultProps: {
        focusBorderColor: '#2f4f6f',
      },
    },
  },
})

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ChakraProvider theme={theme}>
      <App />
    </ChakraProvider>
  </StrictMode>,
)
