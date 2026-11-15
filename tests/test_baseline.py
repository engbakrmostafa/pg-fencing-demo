from fencing import try_acquire, write_result


def test_only_one_session_acquires_leadership(database):
    connect, key = database
    with connect() as first, connect() as second:
        assert try_acquire(first, key) == 1
        assert try_acquire(second, key) is None


def test_a_new_leader_receives_a_larger_epoch(database):
    connect, key = database
    with connect() as first:
        assert try_acquire(first, key) == 1
    with connect() as second:
        assert try_acquire(second, key) == 2


def test_current_leader_can_insert_and_update_results(database):
    connect, key = database
    with connect() as leader, connect() as writer:
        epoch = try_acquire(leader, key)
        write_result(writer, epoch, "scan-1", "first")
        write_result(writer, epoch, "scan-1", "updated")
        assert writer.execute(
            "SELECT epoch, value FROM scheduler_result WHERE job_id = 'scan-1'"
        ).fetchone() == (1, "updated")
