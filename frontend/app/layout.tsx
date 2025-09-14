"use client";

import { MantineProvider } from "@mantine/core";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <MantineProvider
          withGlobalStyles
          withNormalizeCSS
          theme={{
            primaryColor: "blue",
            defaultRadius: "md",
          }}
        >
          {children}
        </MantineProvider>
      </body>
    </html>
  );
}
