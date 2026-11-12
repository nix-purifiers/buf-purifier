use prost::Message;
use proof_schemas::purifier::proof::v1::{Answer, Common};
fn main() {
    let mut original = Answer::default();
    original.common = Some(Common { value: 42 });
    original.timestamp.get_or_insert_with(Default::default).seconds = 43;
    let wire = original.encode_to_vec();
    let decoded = Answer::decode(wire.as_slice()).unwrap();
    assert_eq!(decoded.common.unwrap().value, 42);
    assert_eq!(decoded.timestamp.unwrap().seconds, 43);
    print!("42:43:");
    for byte in wire { print!("{:02x}", byte); }
    println!();
}
