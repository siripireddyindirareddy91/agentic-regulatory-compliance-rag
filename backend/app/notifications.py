from sqlalchemy import select
from .models import User,NotificationDelivery
def deliver(db,notification,roles=('admin','reviewer')):
    db.flush()
    for user in db.scalars(select(User).where(User.institution_id==notification.institution_id,User.role.in_(roles))):
        db.add(NotificationDelivery(institution_id=user.institution_id,user_id=user.id,notification_id=notification.id))
def visible(db,rows,user):
    output=[]
    for row in rows:
        deliveries=db.scalars(select(NotificationDelivery).where(NotificationDelivery.notification_id==row.id)).all()
        own=next((d for d in deliveries if d.user_id==user.id),None)
        if not deliveries or own:output.append((row,own.read if own else row.read))
    return output
