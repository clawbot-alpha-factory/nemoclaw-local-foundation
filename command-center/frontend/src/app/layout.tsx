import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'NemoClaw Command Center',
  description: 'System management dashboard for NemoClaw Local Foundation',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased">{children}</body>
    </html>
  );
}
