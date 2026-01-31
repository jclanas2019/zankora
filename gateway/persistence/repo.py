from __future__ import annotations
from datetime import datetime
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from gateway.domain.models import Channel, Chat, Message, AgentRun, Event
from gateway.persistence.schema import ChannelRow, ChatRow, MessageRow, AgentRunRow, EventRow

class Repo:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def upsert_channel(self, ch: Channel) -> None:
        row = await self.s.get(ChannelRow, ch.id)
        if row is None:
            row = ChannelRow(id=ch.id, type=ch.type.value, status=ch.status.value, config=ch.config, last_seen=ch.last_seen)
            self.s.add(row)
        else:
            row.type = ch.type.value
            row.status = ch.status.value
            row.config = ch.config
            row.last_seen = ch.last_seen

    async def list_channels(self) -> list[Channel]:
        res = await self.s.execute(select(ChannelRow))
        out: list[Channel] = []
        for r in res.scalars().all():
            out.append(Channel(id=r.id, type=r.type, status=r.status, config=r.config, last_seen=r.last_seen))
        return out

    async def upsert_chat(self, chat: Chat) -> None:
        row = await self.s.get(ChatRow, chat.chat_id)
        if row is None:
            self.s.add(ChatRow(chat_id=chat.chat_id, channel_id=chat.channel_id, participants=chat.participants, meta=chat.metadata))
        else:
            row.channel_id = chat.channel_id
            row.participants = chat.participants
            row.meta = chat.metadata

    async def list_chats(self, channel_id: str | None = None) -> list[Chat]:
        stmt = select(ChatRow)
        if channel_id:
            stmt = stmt.where(ChatRow.channel_id == channel_id)
        res = await self.s.execute(stmt)
        return [Chat(chat_id=r.chat_id, channel_id=r.channel_id, participants=r.participants, metadata=r.meta) for r in res.scalars().all()]

    async def add_message(self, msg: Message) -> None:
        self.s.add(MessageRow(
            msg_id=msg.msg_id, chat_id=msg.chat_id, channel_id=msg.channel_id,
            sender_id=msg.sender_id, text=msg.text, timestamp=msg.timestamp,
            attachments=[a.model_dump() for a in msg.attachments],
            meta=msg.metadata,
        ))

    async def list_messages(self, chat_id: str, limit: int = 50) -> list[Message]:
        stmt = select(MessageRow).where(MessageRow.chat_id == chat_id).order_by(desc(MessageRow.timestamp)).limit(limit)
        res = await self.s.execute(stmt)
        rows = list(res.scalars().all())
        # reverse to chronological
        rows.reverse()
        from gateway.domain.models import AttachmentMeta
        out: list[Message] = []
        for r in rows:
            out.append(Message(
                msg_id=r.msg_id, chat_id=r.chat_id, channel_id=r.channel_id, sender_id=r.sender_id,
                text=r.text, timestamp=r.timestamp,
                attachments=[AttachmentMeta(**a) for a in (r.attachments or [])],
                metadata=r.meta or {},
            ))
        return out

    async def upsert_run(self, run: AgentRun) -> None:
        row = await self.s.get(AgentRunRow, run.run_id)
        if row is None:
            self.s.add(AgentRunRow(
                run_id=run.run_id, chat_id=run.chat_id, channel_id=run.channel_id,
                requested_by=run.requested_by, status=run.status.value,
                started_at=run.started_at, finished_at=run.finished_at,
                summary=run.summary, output_text=run.output_text
            ))
        else:
            row.status = run.status.value
            row.started_at = run.started_at
            row.finished_at = run.finished_at
            row.summary = run.summary
            row.output_text = run.output_text

    async def get_run(self, run_id: str) -> AgentRun | None:
        row = await self.s.get(AgentRunRow, run_id)
        if not row:
            return None
        return AgentRun(
            run_id=row.run_id, chat_id=row.chat_id, channel_id=row.channel_id,
            requested_by=row.requested_by, status=row.status,
            started_at=row.started_at, finished_at=row.finished_at,
            summary=row.summary, output_text=row.output_text
        )

    async def add_event(self, evt: Event) -> None:
        self.s.add(EventRow(run_id=evt.run_id, seq=evt.seq, type=evt.type.value, payload=evt.payload, ts=evt.ts))

    async def tail_events(self, run_id: str | None, after_seq: int | None, limit: int = 200) -> list[Event]:
        stmt = select(EventRow).order_by(desc(EventRow.seq)).limit(limit)
        if run_id:
            stmt = stmt.where(EventRow.run_id == run_id)
        if after_seq is not None:
            stmt = stmt.where(EventRow.seq > after_seq)
        res = await self.s.execute(stmt)
        rows = list(res.scalars().all())
        rows.reverse()
        from gateway.domain.models import EventType
        return [Event(run_id=r.run_id, seq=r.seq, type=EventType(r.type), payload=r.payload or {}, ts=r.ts) for r in rows]
