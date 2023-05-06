create table linkcomment(
    id varchar(36) primary key,
    link text not null,
    comment text not null,
    username varchar(100) not null,
    created_at real not null,
    updated_at real
);