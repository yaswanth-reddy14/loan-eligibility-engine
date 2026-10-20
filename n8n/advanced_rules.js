const envelope = $json;
const fields = ['minimum_monthly_income','minimum_credit_score','age_min','age_max','employment_requirements'];
if (!Array.isArray(envelope.candidates) || envelope.candidates.length > 50000) {
  throw new Error('Candidate limit exceeded; partition this job before matching');
}
const evaluations = envelope.candidates.map(candidate => {
  const unknown = fields.filter(field => candidate[field] === null);
  unknown.push(...(candidate.qualitative_requirements || []));
  if (!candidate.criteria_complete) unknown.push('Incomplete source criteria');
  return {user_id:candidate.user_id, product_id:candidate.product_id,
    status:unknown.length ? 'REVIEW_REQUIRED' : 'POSSIBLY_ELIGIBLE'};
});
return [{json:{job_id:envelope.job_id, evaluations}}];
