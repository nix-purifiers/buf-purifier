package main
import (
 "fmt"
 "encoding/json"
 "strconv"
 "os"
 "reflect"
 "runtime"
 "time"
 proof "example.org/proof/purifier/proof/v1"
 "google.golang.org/protobuf/proto"
 "google.golang.org/protobuf/types/known/timestamppb"
)
func main(){
 a:=&proof.Answer{Common:&proof.Common{Value:42},Timestamp:timestamppb.New(time.Unix(43,0))}
 wire,err:=proto.Marshal(a);if err!=nil{panic(err)}
 b:=new(proof.Answer);if err=proto.Unmarshal(wire,b);err!=nil{panic(err)}
 if b.GetCommon().GetValue()!=42 || b.GetTimestamp().GetSeconds()!=43{panic("wrong native roundtrip")}
 field:=proof.File_purifier_proof_v1_common_proto.Messages().ByName("Common").Fields().ByName("value").Number()
 expected,err:=strconv.Atoi(os.Args[2]);if err!=nil || int(field)!=expected{panic("wrong schema")}
 fn:=runtime.FuncForPC(reflect.ValueOf(proto.Unmarshal).Pointer());file,_:=fn.FileLine(fn.Entry());
 fmt.Printf("%d:%d:%d:%x\n",b.GetCommon().GetValue(),b.GetTimestamp().GetSeconds(),field,wire)
 own:=runtime.FuncForPC(reflect.ValueOf((*proof.Common).GetValue).Pointer());owned,_:=own.FileLine(own.Entry())
 data,err:=json.Marshal(map[string]string{"runtime":file,"owned":owned});if err!=nil{panic(err)}
 if err=os.WriteFile(os.Args[1],data,0644);err!=nil{panic(err)}
}
