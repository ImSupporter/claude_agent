UPDATE users
SET status = :new_status, updated_at = NOW()
WHERE user_id = :user_id
