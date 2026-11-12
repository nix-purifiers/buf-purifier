package main
import (
 "fmt"
 "os"
 "runtime"
 "reflect"
 proof "example.org/proof/purifier/proof/v1"
 foreign "example.org/foreign/foreign/proof/v1"
 "google.golang.org/protobuf/proto"
)
func main(){
 a:=&proof.Answer{Foreign:&foreign.Foreign{Value:77}}
 wire,err:=proto.Marshal(a);if err!=nil{panic(err)}
 b:=new(proof.Answer);if err=proto.Unmarshal(wire,b);err!=nil{panic(err)}
 if b.GetForeign().GetValue()!=77{panic("wrong foreign module value")}
 fn:=runtime.FuncForPC(reflect.ValueOf((*foreign.Foreign).GetValue).Pointer());file,_:=fn.FileLine(fn.Entry())
 if err=os.WriteFile(os.Args[1],[]byte(file),0644);err!=nil{panic(err)}
 fmt.Printf("77:%x\n",wire)
}
