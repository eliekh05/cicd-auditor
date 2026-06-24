export default function PipelineViewer({ pipeline }) {
  return (
    <div className="pipeline-viewer">
      <div className="pipeline-meta">
        <span className="pipeline-type">{pipeline.pipeline_type}</span>
        {pipeline.override_reason && (
          <span className="override-reason">{pipeline.override_reason}</span>
        )}
      </div>
      <pre className="pipeline-code"><code>{pipeline.content}</code></pre>
    </div>
  );
}
