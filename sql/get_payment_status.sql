SELECT p.payment_id, p.amount, p.status, p.created_at, p.error_code
FROM payments p
WHERE p.user_id = :user_id
ORDER BY p.created_at DESC
LIMIT 10
