export default function ReportSection({ title, children }) {
  return (
    <section className="report-section card">
      <h2>{title}</h2>
      {children}
    </section>
  );
}
