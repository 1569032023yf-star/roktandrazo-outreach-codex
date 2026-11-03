"""Private bounded stdio control for a supervised child / 受控子进程私有有界控制流。

No listener, address, credentials, paths or commands. Reader threads only enqueue;
the supervising caller checks authority and sends acknowledgements on its thread.
"""
import json
import queue
import threading

PREFIX = b'U1_MAINTENANCE:'
MAX_REQUEST_BYTES = 2048
MAX_REQUESTS = 4096


class ControlProtocolError(RuntimeError):
    reason = 'MAINTENANCE_CONTROL_PROTOCOL'
    outcome = 'UNKNOWN'


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ControlProtocolError('STOP_AND_PRESERVE_DUPLICATE_CONTROL_KEY')
        result[key] = value
    return result


class MaintenanceControl:
    def __init__(self, handler, writer):
        self.handler = handler
        self.writer = writer
        self.owner = threading.get_ident()
        self.requests = queue.Queue(maxsize=1)
        self.sequence = 0
        self.lock = threading.Lock()
        self.failure = None

    def offer(self, line):
        if not line.startswith(PREFIX):
            return
        with self.lock:
            if self.failure is not None:
                raise self.failure
            try:
                if len(line) > MAX_REQUEST_BYTES:
                    raise ControlProtocolError('STOP_AND_PRESERVE_CONTROL_LENGTH')
                self.requests.put_nowait(line[len(PREFIX):])
            except (queue.Full, ControlProtocolError) as error:
                self.failure = ControlProtocolError('STOP_AND_PRESERVE_CONTROL_OVERLAP_OR_LENGTH')
                raise self.failure from error

    def poll(self):
        try:
            return self._poll()
        except BaseException as error:
            with self.lock:
                if self.failure is None:
                    self.failure = error
            raise

    def _poll(self):
        if threading.get_ident() != self.owner:
            raise ControlProtocolError('STOP_AND_PRESERVE_CONTROL_THREAD')
        with self.lock:
            if self.failure is not None:
                raise self.failure
        try:
            raw = self.requests.get_nowait()
        except queue.Empty:
            return
        try:
            value = json.loads(raw.decode('utf-8'), object_pairs_hook=strict_object,
                               parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        except (ValueError, UnicodeError) as error:
            raise ControlProtocolError('STOP_AND_PRESERVE_CONTROL_JSON') from error
        keys = {'schema', 'sequence', 'target_operation_id', 'source_commit', 'manifest_sha256', 'action'}
        if (type(value) is not dict or set(value) != keys or
                value['schema'] != 'rokt.u1-maintenance-check.v1' or
                type(value['sequence']) is not int or value['sequence'] != self.sequence or
                self.sequence >= MAX_REQUESTS):
            raise ControlProtocolError('STOP_AND_PRESERVE_CONTROL_SEQUENCE_OR_SCHEMA')
        if self.handler(value) is not True:
            raise ControlProtocolError('STOP_AND_PRESERVE_CONTROL_DENIED')
        reply = json.dumps(dict(sequence=self.sequence, held=True), separators=(',', ':')).encode()+b'\n'
        # Nonblocking writer, a <64-byte response and bounded total count. An
        # unread/full input pipe fails closed instead of hanging supervision.
        # Never write arbitrary child-provided data back into the pipe.
        # Reader failure and ACK share the same lock. Check again after the
        # potentially slow authority callback; a known failure can never receive
        # a late ACK. Capture.fail uses this exact lock and sticky failure slot.
        with self.lock:
            if self.failure is not None:
                raise self.failure
            if self.writer.write(reply) != len(reply):
                raise ControlProtocolError('STOP_AND_PRESERVE_CONTROL_SHORT_WRITE')
            self.writer.flush()
            self.sequence += 1

    def assert_drained(self):
        with self.lock:
            if self.failure is not None:
                raise self.failure
            if not self.requests.empty():
                raise ControlProtocolError('STOP_AND_PRESERVE_CONTROL_UNACKNOWLEDGED')
