SELECT user_id, name, email, status, created_at
FROM users
WHERE user_id = :user_id
