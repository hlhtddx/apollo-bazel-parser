PROTO_FILES:=$(wildcard proto/*.proto)
PROTO_GEN_FILES:=$(patsubst %.proto,%_pb2.py,$(PROTO_FILES))

all: $(PROTO_GEN_FILES)
	echo done

$(PROTO_GEN_FILES):$(PROTO_FILES)
	protoc --python_out=. $(PROTO_FILES)

clean:
	rm -rf proto/*_pb2.py
