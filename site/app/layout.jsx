import "./globals.css";

export const metadata = {
  title: "Acuity Broker Intelligence",
  description: "A living registry of forex and CFD broker regulatory intelligence.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
